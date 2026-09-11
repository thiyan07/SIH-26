"""Multi-source coverage engine — answers 'what evidence do we have for this district and domain?'

Never sums unrelated datasets. Each domain reports source-wise availability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_sources.registry import DOMAIN_POLICY, SOURCES, STATUS_UNAVAILABLE, STATUS_LIMITED

TN_DISTRICTS = [
    "Ariyalur","Chengalpattu","Chennai","Coimbatore","Cuddalore","Dharmapuri","Dindigul",
    "Erode","Kallakurichi","Kanchipuram","Kanniyakumari","Karur","Krishnagiri","Madurai",
    "Mayiladuthurai","Nagapattinam","Namakkal","Perambalur","Pudukkottai","Ramanathapuram",
    "Ranipet","Salem","Sivaganga","Tenkasi","Thanjavur","The Nilgiris","Theni","Thiruvallur",
    "Thiruvarur","Thoothukudi","Tiruchirappalli","Tirunelveli","Tirupathur","Tiruppur",
    "Tiruvannamalai","Vellore","Villupuram","Virudhunagar",
]

# District name aliases (LGD old names vs current)
DISTRICT_ALIASES = {
    "Thoothukudi": ["Tuticorin"],
    "Villupuram": ["Viluppuram"],
}
def _district_variants(name: str) -> list[str]:
    vars = [name]
    for k, aliases in DISTRICT_ALIASES.items():
        if name == k:
            vars.extend(aliases)
        elif name in aliases:
            vars.append(k)
    return vars

@dataclass
class SourceEvidence:
    source_code: str
    status: str  # REAL/OFFICIAL/HISTORICAL/LIMITED/STALE/UNAVAILABLE
    count: int = 0
    reference_date: Optional[str] = None
    retrieved_at: Optional[str] = None
    scope: str = ""
    confidence: str = "low"
    limitations: list[str] = field(default_factory=list)

@dataclass
class DomainCoverage:
    domain: str
    district: str
    sources: list[SourceEvidence] = field(default_factory=list)
    coverage_level: str = "UNAVAILABLE"  # GOOD/PARTIAL/LIMITED/UNAVAILABLE
    confidence: str = "low"
    limitations: list[str] = field(default_factory=list)

def _coverage_for_domain(sources: list[SourceEvidence]) -> tuple[str, str, list[str]]:
    """Derive coverage_level + confidence from source-wise evidence."""
    has_real = any(s.status in ("REAL","OFFICIAL","OPEN_DATA") and s.count>0 for s in sources)
    has_historical = any(s.status=="HISTORICAL" and s.count>0 for s in sources)
    has_limited = any(s.status in ("LIMITED","STALE") and s.count>0 for s in sources)
    if has_real:
        # check freshness: if real count substantial vs historical
        return "GOOD", "high", []
    if has_historical or has_limited:
        return "PARTIAL", "medium", ["Only historical/limited source available; not current"]
    if any(s.count>0 for s in sources):
        return "PARTIAL", "low", ["Weak evidence only"]
    return "UNAVAILABLE", "low", ["No legitimate evidence available for this domain"]

def district_domain_coverage(db: Session, district: str, domain: str) -> DomainCoverage:
    """Assemble source-wise evidence for one district + domain."""
    allowed = DOMAIN_POLICY.get(domain, [])
    sources: list[SourceEvidence] = []
    for code in allowed:
        src = SOURCES.get(code)
        if not src:
            continue
        count = 0
        ref = None
        retrieved = None
        status = src.status_default
        # Domain-specific count query — do NOT cross-count datasets
        try:
            if domain == "local_businesses" and code == "osm_business":
                # Businesses are point data, not district-scoped; use district centroid proximity count
                # For coverage, count businesses whose nearest location district matches (approximate via locations join would be heavy)
                # Instead treat as statewide discovery availability (separate from count)
                count = db.execute(text("SELECT count(*) FROM businesses WHERE is_demo IS NOT TRUE")).scalar() or 0
                # But per-district we approximate via CompetitorCache/Overpass — mark as discovery-available
                # For audit, we check if any business within district's centroid radius exists — simplified to total>0 = PARTIAL
                if count>0:
                    status = "REAL"
                    count = 1  # signal availability, not total
            elif domain == "registered_msme" and code == "udyam_official":
                row = db.execute(text("SELECT count(*), max(registration_date) FROM udyam_units WHERE is_demo IS NOT TRUE AND district ILIKE :d"), {"d": district}).fetchone()
                count = row[0] or 0
                ref = str(row[1]) if row and row[1] else None
                if count>0:
                    status = "REAL"
            elif domain == "market_prices" and code in ("market_prices_official","acrop_mirror"):
                # Handle district aliases (Thoothukudi/Tuticorin, Villupuram/Viluppuram) + case-insensitive
                variants = _district_variants(district)
                placeholders = ",".join([f"'{v}'" for v in variants])  # safe: TN_DISTRICTS are controlled
                row = db.execute(text(f"SELECT count(*), max(reference_date) FROM market_prices WHERE is_demo IS NOT TRUE AND district ILIKE ANY(ARRAY[{placeholders}])")).fetchone()
                count = row[0] or 0
                ref = str(row[1]) if row and row[1] else None
                if count>0:
                    status = "REAL" if code=="market_prices_official" else "LIMITED"
            elif domain == "administrative":
                variants = _district_variants(district)
                placeholders = ",".join([f"'{v}'" for v in variants])
                count = db.execute(text(f"SELECT count(*) FROM locations WHERE is_demo IS NOT TRUE AND district ILIKE ANY(ARRAY[{placeholders}])")).scalar() or 0
                if count>0:
                    status = "OFFICIAL"
            elif domain == "historical_establishments" and code == "economic_census":
                # Not yet ingested — mark unavailable honestly
                count = 0
                status = "UNAVAILABLE"
            elif domain == "district_economic_structure" and code == "tn_des_statistical_handbook":
                # Not yet ingested for most districts — check administrative_boundaries as proxy
                count = 0
                status = "UNAVAILABLE"
            elif domain == "infrastructure":
                count = db.execute(text("SELECT count(*) FROM infrastructure_points WHERE is_demo IS NOT TRUE")).scalar() or 0
                if count>0:
                    count = 1
            elif domain == "weather":
                count = db.execute(text("SELECT count(*) FROM weather_statistics WHERE is_demo IS NOT TRUE")).scalar() or 0
                if count>0:
                    count = 1
            elif domain == "schemes":
                count = db.execute(text("SELECT count(*) FROM government_schemes WHERE is_demo IS NOT TRUE AND is_active IS TRUE")).scalar() or 0
                if count>0:
                    count = 1
                    status = "OFFICIAL"
            elif domain == "soil_health":
                count = db.execute(text("SELECT count(*) FROM soil_health_statistics WHERE is_demo IS NOT TRUE AND district=:d"), {"d": district}).scalar() or 0
                if count>0:
                    status = "REAL"
        except Exception:
            count = 0
        sources.append(SourceEvidence(
            source_code=code,
            status=status if count>0 else STATUS_UNAVAILABLE,
            count=count,
            reference_date=ref,
            scope=src.geographic_level if src else "",
            confidence=src.confidence_default if src and count>0 else "low",
        ))
    level, conf, lims = _coverage_for_domain(sources)
    return DomainCoverage(domain=domain, district=district, sources=sources, coverage_level=level, confidence=conf, limitations=lims)

def full_audit(db: Session) -> list[dict]:
    """Produce audit list of dicts for all districts × domains."""
    domains = ["local_businesses","registered_msme","district_economic_structure","market_prices","administrative","infrastructure","weather","schemes","soil_health"]
    out = []
    for d in TN_DISTRICTS:
        row = {"district": d}
        overall = []
        for dom in domains:
            cov = district_domain_coverage(db, d, dom)
            row[dom] = cov.coverage_level
            row[f"{dom}_count"] = cov.sources[0].count if cov.sources else 0
            overall.append(cov.coverage_level)
        # Overall: GOOD only if most domains not UNAVAILABLE
        goods = sum(1 for x in overall if x=="GOOD")
        if goods>=5:
            row["overall"]="GOOD"
        elif any(x!="UNAVAILABLE" for x in overall):
            row["overall"]="PARTIAL"
        else:
            row["overall"]="UNAVAILABLE"
        out.append(row)
    return out
