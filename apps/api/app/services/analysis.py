"""Analysis orchestration: the end-to-end vertical slice.

Collects provenance-bearing evidence, computes deterministic scores and
financials, builds a structured evidence context for the AI layer, and
persists an AnalysisRun.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    Business,
    IndicatorStatistic,
    InfrastructurePoint,
    Location,
    PopulationStatistic,
    WeatherStatistic,
)
from app.engines.business_intelligence import (
    apply_weather_risk,
    monthly_economics,
    monthly_economics_to_dict,
    recommend_products,
    seasonal_intelligence,
)
from app.engines.category_profiles import get_category_profile
from app.engines.competition import analyze as analyze_competition
from app.engines.competition import to_dict as competition_to_dict
from app.engines.cost_templates import get_total_template_cost
from app.engines.finance import derive_financial_plan
from app.engines.health import health_access_evidence
from app.engines.location_features import location_features
from app.engines.market import DEFAULT_SIGNAL_CODES as market_default_signal_codes
from app.engines.market import analyze as analyze_market
from app.engines.prices import derive_price_evidence, price_score_from_evidence
from app.engines.profit import simulate_model
from app.engines.repayment import build_schedule as build_repay_schedule
from app.engines.repayment import repayment_health
from app.engines.score import (
    ConfidenceFactors,
    compute_opportunity,
)
from app.engines.soil import soil_health_evidence
from app.engines.weather import weather_risk_factors
from app.geo import distance_to, geo_backend_name, real_data_condition
from app.provenance import (
    QualityInputs,
    compute_data_quality,
    freshness_for,
)


class AnalysisNotFound(KeyError):
    pass


def _entry(e: Optional[Any]) -> dict:
    """Minimal provenance-bearing dict from an ORM object or None."""
    if e is None:
        return {}
    from app.db.models import ProvenanceMixin

    out = {}
    for f in (
        "id", "source_name", "source_url", "dataset_name", "source_type",
        "reference_date", "reference_year", "retrieved_at", "geographic_level",
        "confidence", "methodology", "is_estimate", "is_demo",
    ):
        if hasattr(e, f):
            v = getattr(e, f)
            if v is not None and not isinstance(v, ProvenanceMixin):
                out[f] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


def _business_competition(db: Session, location: Location, category_code: str) -> dict:
    """Count mapped competitors within 5/10 km and nearest distance."""
    lat, lon = location.latitude, location.longitude
    rows5 = _query_businesses(db, lat, lon, 5.0, category_code)
    rows10 = _query_businesses(db, lat, lon, 10.0, category_code)
    nearest = None
    nearest_dist = None
    for r in rows10:
        d = distance_to(r, lat, lon)
        if nearest_dist is None or d < nearest_dist:
            nearest_dist = d
            nearest = r
    discovery = _live_discovery_evidence(db, lat, lon, category_code)
    result = {
        "mapped_competitors_5km": len(rows5),
        "mapped_competitors_10km": len(rows10),
        "nearest_competitor_km": round(nearest_dist, 2) if nearest_dist is not None else None,
        "nearest_competitor": nearest.name if nearest else None,
        "data_completeness": "medium",
        "note": "OSM mapped businesses may be incomplete.",
        "source": _entry(rows10[0]) if rows10 else {"source_name": "OpenStreetMap", "source_type": "osm"},
        "businesses": [_business_out(r, lat, lon) for r in rows10[:50]],
        "live_discovery": discovery,
    }
    return result


def _business_evidence_profile(
    db: Session, latitude: float, longitude: float, category_code: str, radius_km: float = 5.0
) -> dict:
    """Assess real (non-demo) business evidence near the location.

    Coverage and freshness are derived from the actual ingested business rows
    instead of the hard-coded ``medium``/``unknown`` defaults, so scraped or
    verified listings (e.g. Google Maps vendor records with high/medium
    confidence and fresh ``retrieved_at`` timestamps) count as current,
    higher-coverage evidence.

    Returns:
        coverage:      "high" when at least half of a meaningful set of nearby
                       real businesses are fresh vendor/geo records with
                       high/medium confidence; otherwise "medium" (never
                       claims exhaustive coverage or invents data).
        freshness:     freshness bucket of the newest real record in the area.
        real_count / verified_ratio / source_counts / newest_retrieved_at:
                       provenance detail for the confidence explanations.
    """
    from app.db.models import Business
    from app.geo import find_nearby

    rows = find_nearby(
        db, Business, latitude, longitude, radius_km, {"category_code": category_code}, limit=300
    )
    real = [r for r in rows if not getattr(r, "is_demo", False)]
    if not real:
        return {
            "coverage": "medium",
            "freshness": freshness_for(source_type="business"),
            "real_count": 0,
            "verified_ratio": 0.0,
            "source_counts": {},
            "newest_retrieved_at": None,
        }

    source_counts: dict[str, int] = {}
    verified = 0
    newest = None
    for r in real:
        src = (r.source_name or "").strip() or (r.source_type or "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        # Verified, current, higher-confidence records (vendor/geo scraped
        # listings, mapped OSM) count as strong evidence; raw low-confidence
        # or demo rows do not.
        if r.confidence in ("high", "medium") or r.source_type in ("vendor", "osm"):
            verified += 1
        if r.retrieved_at is not None and (newest is None or r.retrieved_at > newest):
            newest = r.retrieved_at

    verified_ratio = verified / len(real)
    coverage = "high" if (verified_ratio >= 0.5 and len(real) >= 5) else "medium"
    freshness = freshness_for(
        source_type="business", reference_date=(newest.date() if newest else None)
    )
    return {
        "coverage": coverage,
        "freshness": freshness,
        "real_count": len(real),
        "verified_ratio": round(verified_ratio, 2),
        "source_counts": source_counts,
        "newest_retrieved_at": newest.isoformat() if newest else None,
    }


def _live_discovery_evidence(db: Session, lat: float, lon: float, category_code: str) -> dict:
    """Best-effort live competitor discovery evidence for the AI layer.

    Runs the on-demand Overpass discovery against the exact lat/lon/radius and
    returns a compact, provenance-carrying evidence block (plan §23). Never
    blocks analysis: any failure / timeout yields an availability marker with
    no fabricated competitors.
    """
    if not lat or not lon:
        return {"available": False, "reason": "no_coordinates"}
    try:
        from app.services.competitors import discover_competitors

        r = discover_competitors(db, latitude=lat, longitude=lon, category_code=category_code)
    except Exception as exc:  # network timeouts, mirror failures, etc.
        return {
            "available": False,
            "reason": "discovery_unavailable",
            "detail": str(exc)[:200],
            "note": "Live competitor discovery could not complete; competitor counts are "
                    "still reported from the static evidence only.",
        }
    comp = r["competitors"]
    direct = comp.get("direct") or 0
    return {
        "available": True,
        "source": r["data"]["primary_source"],
        "source_code": r["data"].get("source", "osm"),
        "mirror": r["data"].get("mirror"),
        "retrieved_at": r["data"].get("retrieved_at"),
        "freshness": r["data"].get("freshness"),
        "data_status": r["data_status"],
        "search_radius_m": r.get("search_radius_m"),
        "coverage": r["confidence"].get("label"),
        "confidence": r["confidence"].get("score"),
        "total_mapped": comp.get("total_mapped"),
        "direct": direct,
        "indirect": comp.get("indirect"),
        "unrelated": comp.get("unrelated"),
        "nearest_km": comp.get("nearest_km"),
        "rings": comp.get("rings"),
        "category_saturation": comp.get("category_saturation"),
        "note": r["data"].get("note"),
        "counts_have_uncertainty": bool(r.get("data_uncertain", False))
        or r["data_status"] in ("UNAVAILABLE", "FRESH_EMPTY", "STALE_CACHE"),
    }


def _query_businesses(db: Session, lat: float, lon: float, radius: float, category_code: str):
    from app.geo import find_nearby
    return find_nearby(db, Business, lat, lon, radius, {"category_code": category_code}, limit=300)


def _business_out(b: Any, lat: float, lon: float) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "category_code": b.category_code,
        "latitude": b.latitude,
        "longitude": b.longitude,
        "distance_km": round(distance_to(b, lat, lon), 2),
        "source_name": b.source_name,
        "source_type": b.source_type,
        "confidence": b.confidence,
        "retrieved_at_date": (b.retrieved_at.date().isoformat() if b.retrieved_at else None),
    }


def _population(db: Session, location: Location) -> dict:
    stmt = select(PopulationStatistic).where(
        PopulationStatistic.location_id == location.id,
        real_data_condition(PopulationStatistic),
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return {
            "population": None,
            "households": None,
            "workers": None,
            "non_workers": None,
            "census_year": 2011,
            "available": False,
            "note": "Population unavailable - Census 2011 baseline not loaded.",
            "source_name": "Census India (expected)",
        }
    return {
        "population": row.population,
        "households": row.households,
        "males": row.males,
        "females": row.females,
        "sex_ratio": row.sex_ratio,
        "literacy": row.literacy,
        "workers": row.workers,
        "non_workers": row.non_workers,
        "census_year": row.census_year or 2011,
        "available": True,
        "is_historical": True,
        "note": f"Census {row.census_year or 2011} baseline - NOT current population.",
        "source_name": row.source_name,
        "dataset_name": row.dataset_name,
        "source_type": row.source_type,
        "confidence": row.confidence,
        "is_demo": bool(row.is_demo),
        "is_estimate": bool(row.is_estimate),
    }


def _infrastructure(db: Session, location: Location) -> dict:
    lat, lon = location.latitude, location.longitude
    from app.geo import find_nearby

    markets = find_nearby(db, InfrastructurePoint, lat, lon, 20.0, {"kind": "market"}, limit=20)
    transport = find_nearby(db, InfrastructurePoint, lat, lon, 20.0, {"kind": "transport"}, limit=20)
    health = health_access_evidence(db, lat, lon)
    nearest_market = min((distance_to(m, lat, lon) for m in markets), default=None)
    nearest_transport = min((distance_to(t, lat, lon) for t in transport), default=None)
    return {
        "nearest_market_km": round(nearest_market, 2) if nearest_market else None,
        "nearest_transport_km": round(nearest_transport, 2) if nearest_transport else None,
        "markets_nearby": len(markets),
        "transport_points": len(transport),
        "nearest_health_km": health.get("nearest_health_km"),
        "health_facilities_nearby": health.get("health_facilities_nearby"),
        "health_available": health.get("available"),
        "nearest_health": health.get("nearest_health"),
    }


def _weather(db: Session, location: Location) -> dict:
    stmt = select(WeatherStatistic).where(
        WeatherStatistic.location_id == location.id,
        real_data_condition(WeatherStatistic),
    ).limit(20)
    rows = list(db.execute(stmt).scalars())
    records = [_entry(r) | {"indicator": r.indicator, "value": r.value} for r in rows]
    return {
        "records": records,
        "available": bool(rows),
        # Phase 7: named, explained weather-risk flags built only from stored rows.
        "risk": weather_risk_factors(records),
    }


def _price_potential(db: Session, category_code: str, district: str) -> dict:
    # Verified provider: reads only ingested MarketPrice rows (provenance-
    # bearing mandi snapshots). Never fabricates prices.
    return derive_price_evidence(db, district=district, category_code=category_code)


def _industry_context(db: Session, state: str) -> dict:
    """Background national/state industry indicators (indicator_statistics).

    Category-scoped, reference data (pesticide, textiles exports, retail
    outlets). Read as context for the report; never fabricated. Returns
    available=False when no rows exist for the state or the national set.
    """
    rows = db.execute(
        select(IndicatorStatistic).where(real_data_condition(IndicatorStatistic))
    ).scalars().all()
    by_indicator: dict[str, list] = {}
    for r in rows:
        if r.state and r.state != state:
            continue
        by_indicator.setdefault(r.indicator, []).append({
            "period": r.period,
            "dimension": r.dimension,
            "value": float(r.value) if r.value is not None else None,
            "unit": r.unit,
            "state": r.state,
        })
    available = bool(by_indicator)
    return {
        "available": available,
        "scope": "national & state background",
        "indicators": {
            k: {"rows": v[:5]}
            for k, v in by_indicator.items()
        },
    }


def run_analysis(db: Session, req) -> dict:
    """Execute the full deterministic pipeline for an AnalysisRequest."""
    from app.log import log_event

    log_event("analysis", step="start",
              state=req.state, district=req.district, block=req.block,
              village=req.village, category_code=req.category_code,
              capital_available=float(req.capital_available))

    location = _resolve_location(db, req.state, req.district, req.block, req.village)
    if location is None:
        raise ValueError("location not found for the given administrative selection")

    # The geospatial centre of all near-distance queries. When the user has
    # pinned an exact shop location on the map, those exact coordinates are
    # used; otherwise fall back to the selected admin area's baseline centroid.
    # The admin `Location` (population, weather, provenance) stays resolution-
    # aware: only the lat/lng used for distance math differ.
    location_view = _geo_center_view(location, getattr(req, "proposed_latitude", None),
                                     getattr(req, "proposed_longitude", None))
    uses_proposed = location_view is not location

    log_event("geo", run_id=req.analysis_id if getattr(req, "analysis_id", None) else None,
              location_id=location.id,
              center_latitude=location_view.latitude,
              center_longitude=location_view.longitude,
              uses_proposed_location=bool(uses_proposed),
              business_backend=geo_backend_name(db, Business),
              infrastructure_backend=geo_backend_name(db, InfrastructurePoint))

    capital = float(req.capital_available)
    category = req.category_code
    scale = (req.preferred_scale or "micro") if hasattr(req, "preferred_scale") else "micro"

    # 1. financial plan (scheme routing) — cost-driven. The project cost comes
    # from the business cost template (category + scale), NOT from capital x 10.
    # The beneficiary borrows only what they cannot cover from own capital.
    project_cost = get_total_template_cost(category, scale)
    fin = derive_financial_plan(project_cost, capital)
    scheme = fin.scheme

    # 2. profit model (estimated)
    model_inputs = getattr(req, "model_inputs", None) or {}
    profit = simulate_model(category, model_inputs)

    # 3. deferred debt service: use effective monthly debt service (EMI).
    # Only relevant when there is an actual loan; a self-funded project
    # (own capital >= project cost) has no debt service.
    monthly_debt_service = None
    if scheme is not None and fin.loan_amount > 0:
        schedule = build_repay_schedule(
            principal=fin.loan_amount,
            annual_rate=scheme.interest_rate,
            tenure_years=scheme.tenure_years,
            moratorium_months=scheme.moratorium_months,
            moratorium_mode=scheme.moratorium_mode,
        )
        monthly_debt_service = schedule.monthly_emi_effective

    health = None
    if monthly_debt_service is not None and monthly_debt_service > 0:
        health = repayment_health(
            monthly_profit=profit.outputs.get("estimated_monthly_operating_profit", 0.0),
            monthly_debt_service=monthly_debt_service,
        )
    else:
        health = {"coverage_ratio": None, "label": "N/A",
                  "disclaimer": "No scheme selected; coverage not computed."}

    # 4. competition / market evidence (reusable engines, plan §12-13)
    profile = get_category_profile(db, category)
    # Assess coverage/freshness from the actual nearby business rows so real
    # scraped/verified listings (e.g. Google Maps vendor records) are counted
    # as current, higher-coverage evidence rather than the historical default
    # of "medium"/"unknown".
    biz_evidence = _business_evidence_profile(
        db,
        latitude=location_view.latitude,
        longitude=location_view.longitude,
        category_code=category,
        radius_km=5.0,
    )
    biz_coverage = biz_evidence["coverage"]
    competitor = analyze_competition(
        db, latitude=location_view.latitude, longitude=location_view.longitude,
        category_code=category, radius_km=5.0,
        data_completeness=biz_coverage,
    )
    competition = competition_to_dict(competitor)
    signal_codes = tuple(profile.get("demand_signals") or market_default_signal_codes())
    market_reach = analyze_market(
        db, location=location_view, radius_km=10.0,
        signal_codes=signal_codes,
        data_completeness=biz_coverage,
    )
    market = market_reach.to_dict()
    population = _population(db, location)
    infrastructure = _infrastructure(db, location_view)
    weather = _weather(db, location)
    soil = soil_health_evidence(
        db, state=location.state, district=location.district,
        block=location.block, village=location.village, location_id=location.id,
    )

    # --- Business-intelligence layer (deterministic, labelled ESTIMATED) ---
    # Weather/climate sensitivity gated by category relevance.
    weather_intelligence = apply_weather_risk(category, weather)
    # Seasonal demand intelligence + product recommendations.
    seasonal = seasonal_intelligence(category)
    products = recommend_products(category)
    # Monthly economics built from the estimated operating model revenue and
    # the actual deferred debt service (EMI) when a loan is present.
    model_revenue = profit.outputs.get("monthly_revenue")
    econ_emi = monthly_debt_service if monthly_debt_service is not None else 0.0
    economics = monthly_economics(
        category,
        monthly_revenue=model_revenue,
        emi=econ_emi,
    )
    # Location-scoped MSME / industrial context (UDYAM pincode-level, factories
    # district-level). Never point-radius competitors; approximate + labelled.
    loc_features = location_features(
        db, state=location.state, district=location.district,
        latitude=location_view.latitude, longitude=location_view.longitude,
        radius_km=10.0, profile=profile,
    )

    industry_ctx = _industry_context(db, location.state)

    # 5. derive component scores (deterministic, evidence-based)
    demand = _demand_score(population, competition, infrastructure)
    comp_score = _competition_score(competition, population)
    acc = _accessibility_score(infrastructure)
    price_evidence = _price_potential(db, category, location.district)
    price = _price_score(price_evidence)
    fin_fit = _financial_fit_score(capital, fin.loan_amount)
    risk = _risk_score(competition, weather, infrastructure, soil)

    years_since_2011 = date.today().year - (population.get("census_year") or 2011) if population.get("available") else None

    result = compute_opportunity(
        demand=demand,
        competition=comp_score,
        accessibility=acc,
        price=price,
        financial_fit=fin_fit,
        risk=risk,
        confidence_factors=ConfidenceFactors(
            population_freshness=years_since_2011,
            business_coverage=competition["data_completeness"],
            geo_precision=location.geo_precision,
        ),
        indicators={
            "competition": competition,
            "population": population,
            "infrastructure": infrastructure,
            "price": price_evidence,
            "soil": soil,
        },
    )

    # 5b. combined data-quality / confidence score (plan §10); per-source freshness
    pop_bucket = freshness_for(
        source_type="population",
        reference_year=population.get("census_year"),
    ) if population.get("available") else "unknown"
    # Business freshness: derived from the newest real record near the
    # location (scraped Google Maps / geo listings carry a retrieved_at
    # timestamp), falling back to "unknown" only when nothing is recorded.
    bus_bucket = biz_evidence["freshness"]
    missing_indicators = []
    if not population.get("available"):
        missing_indicators.append("population")
    if not soil.get("available"):
        missing_indicators.append("soil_health")
    present_slots = (3.0  # base (osm + price + infra-quality)
                     + (1.0 if population.get("available") else 0.0)
                     + (1.0 if soil.get("available") else 0.0)
                     + (0.5 if loc_features.get("available") else 0.0))
    data_quality = compute_data_quality(QualityInputs(
        freshness_buckets=[pop_bucket, bus_bucket],
        geographic_precision=location.geo_precision,
        coverage=competition["data_completeness"],
        completeness=present_slots / 5.5,
        source_reliability="medium",
        any_demo=bool(population.get("is_demo")),
        any_missing_indicators=missing_indicators,
    ))
    log_event("stale",
              population_freshness=pop_bucket,
              business_freshness=bus_bucket,
              years_since_census=years_since_2011,
              location_id=location.id)
    log_event("price",
              category_code=category,
              district=location.district,
              available=price_evidence.get("available"),
              item_count=price_evidence.get("item_count"),
              coverage=price_evidence.get("coverage"),
              price_score=price)
    log_event("soil",
              district=location.district,
              available=soil.get("available"),
              records=soil.get("records"),
              sample_year=soil.get("sample_year"),
              risk_delta=soil.get("risk_delta"))
    log_event("infrastructure",
              location_id=location.id,
              nearest_market_km=infrastructure.get("nearest_market_km"),
              nearest_transport_km=infrastructure.get("nearest_transport_km"),
              nearest_health_km=infrastructure.get("nearest_health_km"),
              health_facilities_nearby=infrastructure.get("health_facilities_nearby"),
              health_source=(infrastructure.get("nearest_health") or {}).get("source_name"))

    evidence = {
        "location": {"id": location.id, "state": location.state, "district": location.district,
                     "block": location.block, "village": location.village,
                     "latitude": location_view.latitude, "longitude": location_view.longitude,
                     "geo_precision": location.geo_precision,
                     "proposed_latitude": getattr(req, "proposed_latitude", None),
                     "proposed_longitude": getattr(req, "proposed_longitude", None),
                     "uses_proposed_location": bool(uses_proposed),
                     "source": _entry(location)},
        "population": population,
        "business_competition": competition,
        "market": market,
        "infrastructure": infrastructure,
        "weather": weather,
        "soil": soil,
        "price": price_evidence,
        "location_features": loc_features,
        "industry_context": industry_ctx,
        "data_confidence": {**data_quality, "business_evidence": biz_evidence},
        "opportunity_score": {
            "overall_score": result.overall_score,
            "demand_score": result.demand_score,
            "competition_score": result.competition_score,
            "accessibility_score": result.accessibility_score,
            "price_score": result.price_score,
            "financial_fit_score": result.financial_fit_score,
            "risk_score": result.risk_score,
            "confidence_score": result.confidence_score,
            "confidence_label": result.confidence_label,
            "confidence_factors": result.confidence_factors,
            "component_breakdown": result.component_breakdown,
            "weights": result.weights,
            "label": "Prototype Opportunity Index",
        },
        "financial_plan": {
            "capital_available": round(capital, 2),
            "project_cost": round(fin.project_cost, 2),
            "own_contribution": round(fin.own_contribution, 2),
            "required_financing": round(fin.required_financing, 2),
            "shortfall": round(fin.shortfall, 2),
            "shortfall_reason": fin.shortfall_reason,
            "loan_amount": round(fin.loan_amount, 2),
            "scale": scale,
            "scheme_code": scheme.code if scheme else None,
            "scheme_name": scheme.name if scheme else None,
            "scheme_decision": fin.scheme_decision,
            "scheme_reason": fin.scheme_reason,
            "max_loan": scheme.max_loan_amount if scheme else None,
            "interest_rate": scheme.interest_rate if scheme else None,
            "tenure_years": scheme.tenure_years if scheme else None,
            "moratorium_months": scheme.moratorium_months if scheme else None,
            "moratorium_mode": scheme.moratorium_mode if scheme else None,
            "source_document": scheme.source_document if scheme else None,
            "notes": fin.notes,
        },
        "repayment": {
            "monthly_emi": round(monthly_debt_service, 2) if monthly_debt_service else None,
            "coverage_ratio": health.get("coverage_ratio"),
            "health_label": health.get("label"),
            "disclaimer": health.get("disclaimer"),
        },
        "profit_model": {
            "category_code": category,
            "label": profit.label,
            "is_estimate": profit.is_estimate,
            "inputs": profit.inputs,
            "outputs": profit.outputs,
            "notes": profit.notes,
        },
        "category_profile": profile,
        "weather_intelligence": weather_intelligence,
        "seasonal_intelligence": seasonal,
        "product_recommendations": products,
        "monthly_economics": monthly_economics_to_dict(economics),
        "recommendation": {
            "label": result.recommendation,
            "reason": result.recommendation_reason,
        },
        "data_sources": _collect_data_sources(competition, population, weather, price_evidence, soil, infrastructure, loc_features),
    }

    # persist
    run = AnalysisRun(
        state=req.state,
        district=req.district,
        block=req.block,
        village=req.village,
        location_id=location.id,
        category_code=category,
        capital_available=round(capital, 2),
        inputs=req.model_dump(),
        result=evidence,
        language=req.language,
    )
    db.add(run)
    db.flush()
    evidence["analysis_id"] = run.id
    run.result = evidence
    db.commit()
    log_event("analysis", run_id=run.id, step="completed",
              location_id=location.id,
              category_code=category,
              overall_score=result.overall_score,
              confidence=result.confidence_label,
              recommendation=result.recommendation,
              stale_population_bucket=pop_bucket,
              stale_business_bucket=bus_bucket)
    return evidence, run


def _resolve_location(db, state, district, block=None, village=None) -> Optional[Location]:
    stmt = select(Location).where(
        Location.state == state,
        Location.district == district,
    )
    if block:
        stmt = stmt.where(Location.block == block)
    if village:
        stmt = stmt.where(Location.village == village)
    stmt = stmt.limit(1)
    return db.execute(stmt).scalars().first()


def _geo_center_view(location: Location, proposed_lat=None, proposed_lng=None):
    """Return a location-like object whose lat/lng drive distance queries.

    When exact proposed shop coordinates are supplied they are used as the
    geospatial centre; otherwise the resolved admin `Location` is returned
    unchanged (identity preserved so callers can tell the difference). The
    object keeps the admin Location's `id` so population/weather lookups,
    which are village- (not point-) scoped, remain keyed to the admin area.
    """
    if proposed_lat is None or proposed_lng is None:
        return location
    view = SimpleNamespace()
    view.id = location.id
    view.state = location.state
    view.district = location.district
    view.block = location.block
    view.village = location.village
    view.geo_precision = location.geo_precision
    view.latitude = proposed_lat
    view.longitude = proposed_lng
    return view


def _demand_score(population: dict, competition: dict, infrastructure: dict) -> Optional[float]:
    score = 50.0
    covered = True
    if population.get("available"):
        pop = population.get("population")
        hh = population.get("households")
        if pop and pop > 0:
            score = min(100.0, 40 + (pop / 5000.0) * 30)  # population demand proxy
        if hh:
            score = min(100.0, score + 5)
    else:
        covered = False
    # market access raises demand estimate
    if infrastructure.get("nearest_market_km") is not None and infrastructure["nearest_market_km"] <= 10:
        score = min(100.0, score + 8)
    return None if not covered else round(score, 1)


def _competition_score(competition: dict, population: dict) -> Optional[float]:
    c5 = competition.get("mapped_competitors_5km") or 0
    c10 = competition.get("mapped_competitors_10km") or 0
    if c5 == 0 and c10 == 0:
        # no mapped competitors -> high competition advantage (low competition)
        return 80.0
    # fewer competitors = higher advantage; scale by density
    base = 100.0 - min(100.0, c10 * 6.0)
    return round(max(5.0, base), 1)


def _accessibility_score(infrastructure: dict) -> Optional[float]:
    score = 50.0
    nm = infrastructure.get("nearest_market_km")
    nt = infrastructure.get("nearest_transport_km")
    if nm is not None:
        if nm <= 3:
            score += 25
        elif nm <= 10:
            score += 12
        else:
            score -= 10
    if nt is not None:
        if nt <= 5:
            score += 10
        elif nt <= 15:
            score += 5
    # public-health access is only rewarded/penalised when real facilities exist
    # (never scores on absence of data):
    nh = infrastructure.get("nearest_health_km")
    if nh is not None:
        if nh <= 5:
            score += 8
        elif nh <= 10:
            score += 4
        else:
            score -= 6
    return round(max(0.0, min(100.0, score)), 1)


def _price_score(evidence: dict) -> Optional[float]:
    return price_score_from_evidence(evidence)


def _financial_fit_score(capital: float, loan_amount: float) -> float:
    project_need = capital + loan_amount
    if project_need <= 0:
        return 50.0
    fit = 100.0 - min(100.0, max(0.0, (loan_amount / project_need) * 30))  # lower reliance on loan = better fit
    return round(fit, 1)


def _risk_score(competition: dict, weather: dict, infrastructure: dict,
                soil: Optional[dict] = None) -> float:
    risk = 30.0
    c5 = competition.get("mapped_competitors_5km") or 0
    if c5 >= 10:
        risk += 25
    elif c5 >= 5:
        risk += 12
    elif c5 >= 3:
        risk += 5
    nm = infrastructure.get("nearest_market_km")
    if nm is not None and nm > 15:
        risk += 15
    nh = infrastructure.get("nearest_health_km")
    if nh is not None and nh > 15:
        risk += 12
    if weather.get("available") is False:
        risk += 5
    else:
        risk += weather.get("risk", {}).get("risk_delta", 0)
    if soil and soil.get("available"):
        risk += soil.get("risk_delta", 0)
    return round(max(0.0, min(100.0, risk)), 1)


def _collect_data_sources(competition: dict, population: dict, weather: dict,
                          price: Optional[dict] = None,
                          soil: Optional[dict] = None,
                          infrastructure: Optional[dict] = None,
                          loc_features: Optional[dict] = None) -> list[dict]:
    sources = []
    if population.get("available"):
        if population.get("is_demo"):
            sources.append({
                "name": population.get("source_name") or "Demo population",
                "dataset": population.get("dataset_name") or "seed_demo",
                "reference_year": population.get("census_year"),
                "confidence": population.get("confidence") or "low",
                "is_demo": True,
                "is_historical": True,
                "note": "Demo proxy population, NOT official Census figures.",
            })
        else:
            sources.append({"name": "Census India", "dataset": "Primary Census Abstract",
                            "reference_year": population.get("census_year"),
                            "confidence": "high", "is_historical": True,
                            "note": "Census 2011 baseline"})
    else:
        sources.append({"name": "Population", "confidence": "low",
                        "note": "Census 2011 baseline not loaded."})
    sources.append({"name": "OpenStreetMap", "dataset": "Business/POI",
                    "confidence": competition.get("data_completeness"),
                    "note": "Mapped data may be incomplete"})
    if price and price.get("available"):
        sources.append({"name": "Mandi prices (verified)", "dataset": "market_prices",
                        "reference_dates": price.get("reference_dates"),
                        "confidence": price.get("confidence"),
                        "note": "Ingested market price rows; never fabricated"})
    if weather.get("available"):
        sources.append({"name": "Weather provider", "confidence": "medium"})
    if soil and soil.get("available"):
        sources.append({"name": "Soil Health Card (MOAFW)",
                        "dataset": "Soil Health Card - Soil Nutrient Analysis",
                        "reference_year": soil.get("sample_year"),
                        "confidence": "medium",
                        "note": soil.get("note") or "Ingested soil nutrient rows; never fabricated"})
    if infrastructure and infrastructure.get("nearest_health") is not None:
        health_src = infrastructure["nearest_health"]
        sources.append({
            "name": "Health facilities",
            "dataset": "infrastructure_points (hospital)",
            "confidence": health_src.get("confidence") or "medium",
            "note": "Official NIC health establishments (GODL-India, via Bharat Atlas) "
                    "plus mapped OSM hospitals; nearest-facility provenance attached to evidence",
        })
    if loc_features and loc_features.get("available"):
        sources.append({
            "name": "UDYAM (Ministry of MSME)",
            "dataset": "List of MSME Registered Units under UDYAM",
            "confidence": loc_features.get("confidence") or "medium",
            "geo_resolution": "pincode",
            "note": "Pincode-centroid MSME context (nearby/relevant units) - "
                    "approximate, not point-located; never used as point competitors.",
        })
    if not sources:
        sources.append({"name": "No verified sources loaded", "confidence": "low"})
    return sources
