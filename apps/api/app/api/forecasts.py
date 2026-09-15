"""Six-month forecasting + Actual vs Predicted + Scenarios."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import Business, BusinessMetric, Forecast, ForecastObservation, Scenario
from app.db.session import get_db
from app.engines.forecasting import forecast_6m

router = APIRouter(prefix="/user/businesses/{business_id}/forecasts", tags=["forecasts"])


class CreateForecastRequest(BaseModel):
    horizon_months: int = Field(default=6, ge=1, le=12)
    business_type: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_forecast(business_id: str, body: CreateForecastRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    # Load history sorted
    history_rows = list(db.execute(select(BusinessMetric).where(BusinessMetric.business_id == business_id).order_by(BusinessMetric.period)).scalars())
    history = [
        {"period": r.period, "revenue": float(r.revenue) if r.revenue else None, "expenses": float(r.expenses) if r.expenses else None, "profit": float(r.profit) if r.profit else None, "cash_surplus": float(r.cash_surplus) if r.cash_surplus else None}
        for r in history_rows
    ]
    result = forecast_6m(history=history, horizon=body.horizon_months, business_type=body.business_type or b.category_code)

    # Determine target_from as next month after last metric, or next month from today
    from datetime import date as _date
    today = _date.today()
    target_from = date.fromisoformat(result["target_from"])
    target_to = date.fromisoformat(result["target_to"])

    # Check for existing forecast with same target_from (unique)
    existing = db.execute(select(Forecast).where(Forecast.business_id == business_id, Forecast.target_from == target_from)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Forecast for this target period already exists")

    fc = Forecast(
        business_id=business_id,
        user_id=current_user.id,
        horizon_months=body.horizon_months,
        model_key=result["model_key"],
        model_version=result["model_version"],
        training_from=date.fromisoformat(result["training_from"]) if result["training_from"] else None,
        training_to=date.fromisoformat(result["training_to"]) if result["training_to"] else None,
        target_from=target_from,
        target_to=target_to,
        inputs=result["inputs"],
        outputs=result["outputs"],
        uncertainty=result["uncertainty"],
        status="published",
    )
    db.add(fc)
    db.commit()
    db.refresh(fc)
    return {
        "id": fc.id,
        "model_key": fc.model_key,
        "model_version": fc.model_version,
        "target_from": fc.target_from.isoformat(),
        "target_to": fc.target_to.isoformat(),
        "outputs": fc.outputs,
        "uncertainty": fc.uncertainty,
        "note": result["note"],
    }


@router.get("")
def list_forecasts(business_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.get(Business, business_id)
    if not b or b.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    rows = list(db.execute(select(Forecast).where(Forecast.business_id == business_id).order_by(Forecast.target_from.desc())).scalars())
    return [
        {"id": r.id, "model_key": r.model_key, "target_from": r.target_from.isoformat(), "target_to": r.target_to.isoformat(), "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@router.get("/{forecast_id}")
def get_forecast(business_id: str, forecast_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    fc = db.get(Forecast, forecast_id)
    if not fc or fc.business_id != business_id or fc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found")
    return {
        "id": fc.id,
        "model_key": fc.model_key,
        "model_version": fc.model_version,
        "target_from": fc.target_from.isoformat(),
        "target_to": fc.target_to.isoformat(),
        "inputs": fc.inputs,
        "outputs": fc.outputs,
        "uncertainty": fc.uncertainty,
        "note": "Forecast with uncertainty, not a guarantee.",
    }


class CreateObservationRequest(BaseModel):
    period: date
    metric: str = Field(pattern="^(revenue|profit|cash|demand)$")
    actual_value: float


@router.post("/{forecast_id}/observations", status_code=status.HTTP_201_CREATED)
def add_observation(business_id: str, forecast_id: str, body: CreateObservationRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    fc = db.get(Forecast, forecast_id)
    if not fc or fc.business_id != business_id or fc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found")
    # Find forecast value
    idx = None
    # Determine index of period in forecast horizon
    from datetime import date as _date
    # Simple: period must be within target_from..target_to
    if body.period < fc.target_from or body.period > fc.target_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Period outside forecast horizon")
    # Find forecast value for metric
    # Outputs are lists indexed by months from target_from
    # Compute month offset
    months_diff = (body.period.year - fc.target_from.year) * 12 + (body.period.month - fc.target_from.month)
    if months_diff < 0 or months_diff >= fc.horizon_months:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Period out of horizon")
    forecast_val = None
    try:
        forecast_val = fc.outputs.get(body.metric, [None] * fc.horizon_months)[months_diff]
    except Exception:
        forecast_val = None
    error_pct = None
    if forecast_val is not None and body.actual_value is not None and forecast_val != 0:
        error_pct = round((body.actual_value - forecast_val) / abs(forecast_val) * 100, 2)
    # Check duplicate
    exists = db.execute(select(ForecastObservation).where(ForecastObservation.forecast_id == forecast_id, ForecastObservation.period == body.period, ForecastObservation.metric == body.metric)).scalars().first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Observation already exists for this period/metric")
    obs = ForecastObservation(
        forecast_id=forecast_id,
        business_id=business_id,
        period=body.period,
        metric=body.metric,
        forecast_value=forecast_val,
        actual_value=body.actual_value,
        error_pct=error_pct,
        collected_at=datetime.now(timezone.utc),
        source="manual",
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return {"id": obs.id, "forecast_value": obs.forecast_value, "actual_value": obs.actual_value, "error_pct": obs.error_pct}


@router.get("/{forecast_id}/observations")
def list_observations(business_id: str, forecast_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    fc = db.get(Forecast, forecast_id)
    if not fc or fc.business_id != business_id or fc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found")
    rows = list(db.execute(select(ForecastObservation).where(ForecastObservation.forecast_id == forecast_id).order_by(ForecastObservation.period)).scalars())
    # Compute MAE/RMSE/MAPE for this forecast
    import math
    errors = [abs(float(r.actual_value) - float(r.forecast_value)) for r in rows if r.actual_value is not None and r.forecast_value is not None]
    mae = round(sum(errors) / len(errors), 2) if errors else None
    rmse = round(math.sqrt(sum(e * e for e in errors) / len(errors)), 2) if errors else None
    mapes = []
    for r in rows:
        if r.actual_value is not None and r.forecast_value not in (None, 0):
            mapes.append(abs(float(r.actual_value) - float(r.forecast_value)) / abs(float(r.forecast_value)) * 100)
    mape = round(sum(mapes) / len(mapes), 2) if mapes else None
    return {
        "observations": [
            {"id": r.id, "period": r.period.isoformat(), "metric": r.metric, "forecast_value": float(r.forecast_value) if r.forecast_value else None, "actual_value": float(r.actual_value) if r.actual_value else None, "error_pct": float(r.error_pct) if r.error_pct else None}
            for r in rows
        ],
        "metrics": {"mae": mae, "rmse": rmse, "mape": mape},
    }



