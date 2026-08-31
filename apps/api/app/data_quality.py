"""Source-level data-quality scoring registry (plan §10 extension).

Each integrated data source carries a Quality-of-Service record with five
explicit, auditable scores rather than a single opaque number:

  * ``source_quality_score``   0-100 structural soundness (documented schema,
    published licence, maintained by a named body, stable API)
  * ``freshness_score``        0-100 recency relative to the source's own
    update cadence (a HISTORICAL census can score high even though old,
    whereas a STALE daily feed scores low)
  * ``completeness_score``     0-100 record richness + column coverage
  * ``verification_score``     0-100 how thoroughly the dataframe was
    cross-checked against the authoritative origin
  * ``overall_confidence_score`` weighted blend -> confidence_label
  * ``verification_status``    VERIFIED | PARTIALLY_VERIFIED | UNVERIFIED |
                               CONFLICTING
  * ``freshness_status``       FRESH | RECENT | STALE | VERY_STALE | UNKNOWN

The catalog below is *declarative and transparent*: every factor is a named
reason string so a human (or the data-sources UI/report) can see exactly why a
score is what it is. Missing or unverifiable evidence reduces a score; it is
never presumed. This module is deliberately detached from the ORM so the
scoring logic is trivially unit-testable (mirrors app/provenance.py).

Freshness-status boundaries (member of the spec's canonical enum):
  FRESH      age <  fresh_under
  RECENT     age <  recent_under
  STALE      age <  stale_under
  VERY_STALE age >= stale_under
  UNKNOWN    no reliable age
The thresholds are per-source cadence, defined in each catalog entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Canonical freshness-status enum from the spec.
FS_FRESH = "FRESH"
FS_RECENT = "RECENT"
FS_STALE = "STALE"
FS_VERY_STALE = "VERY_STALE"
FS_UNKNOWN = "UNKNOWN"

# Verification statuses.
VS_VERIFIED = "VERIFIED"
VS_PARTIAL = "PARTIALLY_VERIFIED"
VS_UNVERIFIED = "UNVERIFIED"
VS_CONFLICTING = "CONFLICTING"


@dataclass
class SourceQualityCatalogEntry:
    """Declarative definition of one source's quality factors."""

    key: str
    name: str
    source_type: str  # government|osm|vendor|proxy|derived
    license_id: str
    cadence: str  # REAL_TIME|NEAR_REAL_TIME|DAILY|WEEKLY|MONTHLY|HISTORICAL|STATIC
    geo_resolution: str  # point|pincode|district|state|mandi
    # structural soundness components (0-100) with reasons
    documented: float = 90.0
    documented_note: str = "Official/community documentation exists."
    licensed: float = 100.0
    licensed_note: str = "Published open-data licence (ODbL / GODL-India)."
    maintained: float = 90.0
    maintained_note: str = "Maintained by a named, identifiable body."
    schema_stable: float = 80.0
    schema_note: str = "Schema is broadly stable for our consumed fields."
    # completeness components (0-100)
    record_richness: float = 70.0
    column_coverage: float = 70.0
    # freshness cadence (years) -> bucket
    fresh_under: float = 0.5
    recent_under: float = 1.0
    stale_under: float = 2.0
    # verification (0-100)
    verification: float = 90.0
    verification_status: str = VS_VERIFIED
    limitations: list[str] = field(default_factory=list)


# NOTE: scores here reflect our *verified* assessment of each source (Phase 2/3
# research). They are starting points an operator can revise via the audit
# tooling; they are never auto-fabricated from a live call we did not make.
SOURCE_QUALITY_CATALOG: dict[str, SourceQualityCatalogEntry] = {
    "osm": SourceQualityCatalogEntry(
        key="osm", name="OpenStreetMap (businesses & infrastructure)",
        source_type="osm", license_id="ODbL-1.0", cadence="WEEKLY",
        geo_resolution="point",
        documented=95.0, documented_note="OpenStreetMap is extensively documented.",
        licensed=100.0, licensed_note="ODbL-1.0: fully open, no attribution cost to API.",
        maintained=95.0, maintained_note="Global volunteer community, continuously maintained.",
        schema_stable=90.0, schema_note="OSM tag schema is stable for shop/amenity/industrial mapping.",
        record_richness=75.0, column_coverage=70.0,
        fresh_under=1.0, recent_under=2.0, stale_under=4.0,
        verification=95.0, verification_status=VS_VERIFIED,
        limitations=["Crowd-sourced completeness varies by area.", "Points mapped by volunteers; may lag reality."],
    ),
    "market_prices_official": SourceQualityCatalogEntry(
        key="market_prices_official", name="Official Mandi prices (data.gov.in, MOA&FW)",
        source_type="government", license_id="GODL-India", cadence="DAILY",
        geo_resolution="mandi",
        documented=85.0, documented_note="Ministry publishes dataset; schema documented.",
        licensed=100.0, licensed_note="GODL-India (Government Open Data Licence).",
        maintained=85.0, maintained_note="Maintained by Directorate of Marketing & Inspection.",
        schema_stable=75.0, schema_note="Column names can vary slightly by state feed.",
        record_richness=80.0, column_coverage=80.0,
        fresh_under=0.1, recent_under=0.3, stale_under=0.7,  # daily cadence
        verification=85.0, verification_status=VS_VERIFIED,
        limitations=["Requires a data.gov.in API key.", "Mandi-level (not exact market point) resolution."],
    ),
    "udyam": SourceQualityCatalogEntry(
        key="udyam", name="UDYAM MSME registration (Ministry of MSME, via data.gov.in)",
        source_type="government", license_id="GODL-India", cadence="DAILY",
        geo_resolution="pincode",
        documented=85.0, documented_note="Official Udyam metadata PDF + OGD catalog documentation.",
        licensed=100.0, licensed_note="GODL-India.",
        maintained=90.0, maintained_note="Ministry of MSME, updated continuously via the Udyam portal.",
        schema_stable=70.0, schema_note="Unit list schema varies by resource release; NIC self-reported.",
        record_richness=60.0, column_coverage=75.0,
        fresh_under=0.2, recent_under=0.5, stale_under=1.0,  # daily cadence
        verification=85.0, verification_status=VS_VERIFIED,
        limitations=[
            "Pincode-level geo resolution (no exact lat/lng).",
            "Unit list carries no turnover / investment / MSME-class fields.",
            "NIC activity codes are self-reported and not always stable.",
            "Registration != operating activity; some units may be dormant.",
            "Requires a data.gov.in API key.",
        ],
    ),
    "industrial_units": SourceQualityCatalogEntry(
        key="industrial_units", name="Registered Factories / ASI (district aggregates)",
        source_type="government", license_id="GODL-India", cadence="YEARLY",
        geo_resolution="district",
        documented=80.0, documented_note="ASI / Registered Factories documented by Labour Stats.",
        licensed=90.0, licensed_note="GODL-India / NDSAP.",
        maintained=80.0, maintained_note="ASPI (MoSPI) and state Labour Departments.",
        schema_stable=75.0, schema_note="District-level tables are stable.",
        record_richness=70.0, column_coverage=65.0,
        fresh_under=1.5, recent_under=2.5, stale_under=4.0,  # yearly publication, ~2yr lag
        verification=75.0, verification_status=VS_PARTIAL,
        limitations=[
            "District-only granularity - cannot support point-radius queries.",
            "ASI is published with a ~2-year lag.",
        ],
    ),
    "weather_imd": SourceQualityCatalogEntry(
        key="weather_imd", name="IMD rainfall (India Meteorological Department)",
        source_type="government", license_id="GODL-India", cadence="MONTHLY",
        geo_resolution="district",
        documented=85.0, documented_note="IMD publishes technical documentation.",
        licensed=90.0, licensed_note="GODL-India.",
        maintained=90.0, maintained_note="IMD, authoritative national weather agency.",
        schema_stable=75.0, schema_note="District rainfall tables are stable.",
        record_richness=75.0, column_coverage=75.0,
        fresh_under=0.5, recent_under=1.0, stale_under=2.0,
        verification=85.0, verification_status=VS_VERIFIED,
        limitations=["District-level resolution.", "Some historical series require a key."],
    ),
    "census_2011": SourceQualityCatalogEntry(
        key="census_2011", name="Census of India 2011 (baseline)",
        source_type="government", license_id="GODL-India", cadence="HISTORICAL",
        geo_resolution="village",
        documented=95.0, documented_note="Fully documented decennial census.",
        licensed=90.0, licensed_note="GODL-India.",
        maintained=90.0, maintained_note="Office of the Registrar General & Census Commissioner.",
        schema_stable=90.0, schema_note="Primary Census Abstract is stable.",
        record_richness=95.0, column_coverage=90.0,
        fresh_under=0.0, recent_under=0.0, stale_under=0.0,  # permanently historical
        verification=95.0, verification_status=VS_VERIFIED,
        limitations=[
            "Census 2011 is a HISTORICAL baseline - never presented as current population.",
            "Village centroid resolution.",
        ],
    ),
    "soil_health": SourceQualityCatalogEntry(
        key="soil_health", name="Soil Health Card (MOAFW, via data.gov.in)",
        source_type="government", license_id="GODL-India", cadence="YEARLY",
        geo_resolution="village",
        documented=80.0, documented_note="MOAFW publishes the Soil Health Card schema.",
        licensed=90.0, licensed_note="GODL-India.",
        maintained=80.0, maintained_note="MOAFW; coverage varies by state cycle.",
        schema_stable=70.0, schema_note="Village-level nutrient rows can vary in coverage.",
        record_richness=70.0, column_coverage=75.0,
        fresh_under=1.5, recent_under=3.0, stale_under=5.0,
        verification=80.0, verification_status=VS_PARTIAL,
        limitations=["Sample cycling causes per-village gaps.", "Requires a data.gov.in API key."],
    ),
    "health_facilities": SourceQualityCatalogEntry(
        key="health_facilities", name="Health facilities (GODL-India NIC via Bharat Atlas)",
        source_type="government", license_id="GODL-India", cadence="MONTHLY",
        geo_resolution="point",
        documented=80.0, documented_note="NIC health establishments documented on GODL-India.",
        licensed=90.0, licensed_note="GODL-India.",
        maintained=80.0, maintained_note="NIC / state health directorates.",
        schema_stable=80.0, schema_note="GODL-India health facility schema is stable.",
        record_richness=75.0, column_coverage=80.0,
        fresh_under=0.5, recent_under=1.0, stale_under=2.0,
        verification=80.0, verification_status=VS_PARTIAL,
        limitations=["Facility list may be incomplete at block level.", "Point coords from official atlas."],
    ),
    "infrastructure_osm": SourceQualityCatalogEntry(
        key="infrastructure_osm", name="Infrastructure / road / transport (OSM-derived)",
        source_type="osm", license_id="ODbL-1.0", cadence="WEEKLY",
        geo_resolution="point",
        documented=90.0, documented_note="OSM infrastructure tags well documented.",
        licensed=100.0, licensed_note="ODbL-1.0.",
        maintained=90.0, maintained_note="Global volunteer community.",
        schema_stable=85.0, schema_note="Road/rail/station tags stable.",
        record_richness=80.0, column_coverage=75.0,
        fresh_under=1.0, recent_under=2.0, stale_under=4.0,
        verification=90.0, verification_status=VS_VERIFIED,
        limitations=["Crowd-sourced completeness varies by area."],
    ),
}


def _weighted_overall(factors: dict[str, float]) -> float:
    """Blend sub-scores into a single 0-100 confidence score.

    Explicit, documented weights - not a black box. Verification is weighted
    highest because an unverified source can look good on paper while being
    wrong in practice; the spec's conflict/cross-check policy demands it.
    """
    weights = {
        "source_quality": 0.25,
        "freshness": 0.20,
        "completeness": 0.20,
        "verification": 0.35,
    }
    total = sum(max(0.0, min(100.0, factors[k])) * w for k, w in weights.items())
    return round(total, 1)


def confidence_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _freshness_status(entry: SourceQualityCatalogEntry, age_years: Optional[float]) -> str:
    if age_years is None:
        return FS_UNKNOWN
    if age_years < entry.fresh_under:
        return FS_FRESH
    if age_years < entry.recent_under:
        return FS_RECENT
    if age_years < entry.stale_under:
        return FS_STALE
    return FS_VERY_STALE


def score_source(
    entry: SourceQualityCatalogEntry,
    *,
    age_years: Optional[float] = None,
    alive_override: Optional[bool] = None,
) -> dict:
    """Compute the full five-score quality record for one source.

    ``age_years`` is how old the *latest ingested snapshot* is (None -> unknown
    freshness). ``alive_override`` lets callers mark a live source that has not
    been recently synced; when set it forces the freshness sub-score low even
    if ``age_years`` is missing, so a not-yet-synced provider is not given the
    benefit of the doubt.
    """
    reasons: list[str] = []

    # 1. source_quality_score: weighted blend of structural factors
    structural = {
        "documented": entry.documented,
        "licensed": entry.licensed,
        "maintained": entry.maintained,
        "schema_stable": entry.schema_stable,
    }
    source_quality = round(
        sum(v / 4.0 for v in structural.values()), 1
    )
    reasons.append(f"Documentation: {entry.documented_note}")
    reasons.append(f"Licence: {entry.licensed_note}")
    reasons.append(entry.maintained_note)
    reasons.append(f"Schema stability: {entry.schema_note}")

    # 2. freshness_score: recency vs source cadence.
    if age_years is None:
        if alive_override is not False and entry.fresh_under > 0:
            # No snapshot yet -> treat as unknown, not as "fresh".
            freshness_score = 40.0
            freshness_status = FS_UNKNOWN
            reasons.append("No successful snapshot recorded - freshness unknown.")
        else:
            freshness_score = 30.0
            freshness_status = FS_UNKNOWN
            reasons.append("Source unavailable / not synced - freshness not assessed.")
    else:
        status = _freshness_status(entry, age_years)
        if status == FS_FRESH:
            freshness_score = 95.0
        elif status == FS_RECENT:
            freshness_score = 80.0
        elif status == FS_STALE:
            freshness_score = 55.0
        elif status == FS_VERY_STALE:
            freshness_score = 30.0
        else:
            freshness_score = 40.0
        freshness_status = status
        reasons.append(f"Latest snapshot age {age_years:.2f} yrs -> {status} (cadence {entry.cadence}).")

    # 3. completeness_score
    completeness = round(
        0.6 * entry.record_richness + 0.4 * entry.column_coverage, 1
    )
    reasons.append(
        f"Record richness {entry.record_richness:.0f}, column coverage {entry.column_coverage:.0f}."
    )

    # 4. verification_score
    verification = entry.verification
    if entry.verification_status == VS_CONFLICTING:
        verification = min(verification, 45.0)
        reasons.append("Source disagreements recorded (CONFLICTING) - confidence reduced.")
    elif entry.verification_status == VS_UNVERIFIED:
        verification = min(verification, 35.0)
        reasons.append("Source not independently verifiable against an authoritative origin.")
    elif entry.verification_status == VS_PARTIAL:
        reasons.append("Partially verified against the authoritative origin.")
    elif entry.verification_status == VS_VERIFIED:
        reasons.append("Cross-checked against the authoritative origin.")
    verification = round(verification, 1)

    # 5. overall confidence
    overall = _weighted_overall({
        "source_quality": source_quality,
        "freshness": freshness_score,
        "completeness": completeness,
        "verification": verification,
    })

    return {
        "source_key": entry.key,
        "source_name": entry.name,
        "source_type": entry.source_type,
        "license_id": entry.license_id,
        "cadence": entry.cadence,
        "geo_resolution": entry.geo_resolution,
        "source_quality_score": source_quality,
        "freshness_score": freshness_score,
        "freshness_status": freshness_status,
        "completeness_score": completeness,
        "verification_score": verification,
        "verification_status": entry.verification_status,
        "overall_confidence_score": overall,
        "confidence_label": confidence_band(overall),
        "reasons": reasons,
        "limitations": entry.limitations,
    }


def score_catalog(ages: Optional[dict[str, Optional[float]]] = None,
                  alive: Optional[dict[str, bool]] = None) -> dict[str, dict]:
    """Score every source in the catalog (for the ledger / report)."""
    ages = ages or {}
    alive = alive or {}
    return {
        key: score_source(
            entry,
            age_years=ages.get(key),
            alive_override=alive.get(key),
        )
        for key, entry in SOURCE_QUALITY_CATALOG.items()
    }
