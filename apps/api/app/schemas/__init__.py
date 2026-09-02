"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LocationInput(BaseModel):
    state: str
    district: str
    block: Optional[str] = None
    village: Optional[str] = None


class RagRetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


class RagAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    language: str = Field(default="en", pattern="^(en|ta|hi)$")


class LocationOut(BaseModel):
    id: str
    state: str
    district: str
    block: Optional[str] = None
    village: Optional[str] = None
    latitude: float
    longitude: float
    geo_precision: str = "point"
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    confidence: Optional[str] = None
    reference_year: Optional[int] = None

    class Config:
        from_attributes = True


class BusinessOut(BaseModel):
    id: str
    name: str
    category_code: Optional[str] = None
    subcategory: Optional[str] = None
    latitude: float
    longitude: float
    address: Optional[str] = None
    distance_km: Optional[float] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    confidence: Optional[str] = None
    retrieved_at: Optional[Any] = None

    class Config:
        from_attributes = True


class NearbyBusinessQuery(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=10, gt=0, le=100)
    category_code: Optional[str] = None


class CompetitorQuery(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category_code: str
    radius_km: float = Field(default=5, gt=0, le=100)


class CompetitorDiscoveryQuery(BaseModel):
    """P0 exact-location competitor discovery (map marker is the source of truth)."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category_code: str
    radius_km: Optional[float] = Field(default=None, gt=0, le=20)
    radius_m: Optional[int] = Field(default=None, gt=0, le=20000)


class MSMEClustersQuery(BaseModel):
    """Fetch pincode-centroid clusters of registered UDYAM MSME units near a point.

    MSME units resolve at pincode granularity (the official export carries no
    street coordinates), so each returned cluster is one pincode centroid with
    unit + activity counts. ``include_units`` opts into the per-pincode unit
    list (business names + street addresses) for a drill-down layer.
    """
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=10, gt=0, le=50)
    include_units: bool = False
    max_clusters: int = Field(default=50, ge=1, le=200)


class AnalysisRequest(BaseModel):
    state: str
    district: str
    block: Optional[str] = None
    village: Optional[str] = None
    proposed_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    proposed_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    capital_available: float = Field(gt=0)
    category_code: str
    business_experience: Optional[bool] = None
    existing_shop: Optional[bool] = None
    existing_equipment: Optional[bool] = None
    family_members: Optional[int] = Field(default=None, ge=0)
    preferred_scale: Optional[str] = None
    language: str = Field(default="en", pattern="^(en|ta|hi)$")

    @field_validator("capital_available")
    @classmethod
    def capital_positive(cls, v):
        if v <= 0:
            raise ValueError("capital_available must be positive")
        return v


class FinancialCalculateRequest(BaseModel):
    capital_available: float = Field(gt=0)
    category_code: str
    # optional business model inputs
    model_inputs: Optional[dict[str, Any]] = None


class EmiRequest(BaseModel):
    loan_amount: float = Field(gt=0)
    interest_rate: float = Field(gt=0)
    tenure_years: float = Field(gt=0)
    moratorium_months: int = Field(default=0, ge=0)
    moratorium_mode: str = Field(default="interest_only_during_moratorium")


class SimulateRequest(BaseModel):
    loan_amount: float = Field(gt=0)
    interest_rate: float = Field(gt=0)
    tenure_years: float = Field(gt=0)
    moratorium_months: int = 0
    moratorium_mode: str = "interest_only_during_moratorium"
    baseline_monthly_profit: float = Field(gt=0)
    scenarios: Optional[dict[str, Any]] = None


class SchemeRecommendRequest(BaseModel):
    project_cost: float = Field(gt=0)


class AiAdviceRequest(BaseModel):
    analysis_id: Optional[str] = None
    evidence: Optional[dict[str, Any]] = None
    language: str = Field(default="en", pattern="^(en|ta|hi)$")
    mode: str = Field(default="advice", pattern="^(advice|swot|report|risk)$")


class MarketSummaryQuery(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=10, gt=0, le=100)
    category_code: Optional[str] = None


_LAYER_OPTIONS = {"businesses", "infrastructure", "markets"}


class LayerQuery(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=10, gt=0, le=100)
    layers: Optional[list[str]] = None

    @field_validator("layers")
    @classmethod
    def layers_subset(cls, v):
        if v is None:
            return v
        unknown = set(v) - _LAYER_OPTIONS
        if unknown:
            raise ValueError(f"unsupported layers: {sorted(unknown)} (allowed: {sorted(_LAYER_OPTIONS)})")
        return v
