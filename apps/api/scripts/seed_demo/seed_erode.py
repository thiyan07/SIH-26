"""Seed clearly-labelled DEMO data for Erode District, Tamil Nadu.

All records are flagged is_demo=True and must never be presented as official.
Population values are proxies (not Census figures). Businesses are demo
illustrations. Replace with real ingestion (scripts/ingest_osm, etc.) for
production.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import (
    Business,
    InfrastructurePoint,
    Location,
    PopulationStatistic,
)
from app.db.session import session_scope

# Demo administrative structure for Erode, Tamil Nadu.
# Centres are approximate (village/block centroids) - is_demo=True.
BLOCKS = {
    "Erode": [
        ("Sathyamangalam", 11.5056, 77.2390, {
            "population": 12400, "households": 3400, "males": 6200, "females": 6200,
        }),
        ("Perundurai", 11.2760, 77.5800, {
            "population": 9800, "households": 2700, "males": 4900, "females": 4900,
        }),
        ("Bhavani", 11.4460, 77.6820, {
            "population": 11300, "households": 3100, "males": 5700, "females": 5600,
        }),
        ("Thindal", 11.3200, 77.6760, {
            "population": 10800, "households": 2900, "males": 5400, "females": 5400,
        }),
    ],
}

# Demo mapped businesses. Names are illustrative demo records (is_demo=True).
DEMO_BUSINESSES = {
    "Sathyamangalam": [
        ("Sathya Dairy Supplies", "dairy", 11.5032, 77.2405),
        ("Kongu Fresh Milk", "dairy", 11.5041, 77.2388),
        ("Green Grocers", "grocery", 11.5028, 77.2410),
        ("Anna Bakery", "food_processing", 11.5050, 77.2420),
        ("Village Mart", "grocery", 11.5035, 77.2395),
        ("R.K. Tailors", "textile", 11.5062, 77.2382),
    ],
    "Perundurai": [
        ("Peru Fresh Dairy", "dairy", 11.2748, 77.5812),
        ("KgBazaar Retail", "grocery", 11.2770, 77.5790),
        ("Sai Restaurant", "restaurant", 11.2755, 77.5805),
        ("Balaji Textiles", "textile", 11.2768, 77.5788),
    ],
    "Bhavani": [
        ("Bhavani Dairy Co-op", "dairy", 11.4448, 77.6830),
        ("GRT Milk", "dairy", 11.4472, 77.6810),
        ("Priya Tailors", "textile", 11.4455, 77.6822),
        ("Fresh Food Works", "food_processing", 11.4460, 77.6840),
    ],
    "Thindal": [
        ("Thindal Murugan Dairy", "dairy", 11.3188, 77.6768),
        ("Sakthi Grocery", "grocery", 11.3204, 77.6754),
        ("Cauvery Restaurant", "restaurant", 11.3195, 77.6762),
        ("Kongu Textiles", "textile", 11.3209, 77.6770),
    ],
}

# Demo market / transport infra.
DEMO_MARKETS = {
    "Sathyamangalam": (11.5050, 77.2400),
    "Perundurai": (11.2750, 77.5800),
    "Bhavani": (11.4450, 77.6820),
    "Thindal": (11.3190, 77.6760),
}


def _source(**kw):
    kw.update({
        "source_name": "Demo seed (Erode)",
        "source_type": "demo",
        "dataset_name": "seed_demo_erode",
        "is_demo": True,
        "is_estimate": True,
        "confidence": "low",
        "methodology": "Clear demo illustration; replace with real ingestion.",
    })
    return kw


def seed_demo():
    with session_scope() as s:
        for block, villages in BLOCKS.items():
            for village, lat, lon, pop in villages:
                # Location (centroid precision)
                loc = s.execute(select(Location).where(
                    Location.state == "Tamil Nadu", Location.district == "Erode",
                    Location.block == village, Location.village == village,
                )).scalars().first()
                if loc is None:
                    loc = Location(
                        state="Tamil Nadu", district="Erode", block=village, village=village,
                        latitude=lat, longitude=lon, geo_precision="centroid",
                        **_source(),
                    )
                    s.add(loc)
                    s.flush()

                # Population (demo proxy - NOT Census)
                if not s.execute(select(PopulationStatistic).where(
                        PopulationStatistic.location_id == loc.id)).scalars().first():
                    s.add(PopulationStatistic(
                        location_id=loc.id, level="village", census_year=2011,
                        population=pop["population"], households=pop["households"],
                        males=pop["males"], females=pop["females"],
                        sex_ratio=round(pop["females"] / pop["males"] * 1000, 1),
                        **_source(),
                    ))

                # Businesses
                for name, cat, blat, blon in DEMO_BUSINESSES.get(village, []):
                    existing = s.execute(select(Business).where(Business.name == name)).scalars().first()
                    if existing is None:
                        b = Business(
                            name=name, category_code=cat,
                            latitude=blat, longitude=blon,
                            source="demo",
                            subcategory=cat,
                            address=f"Demo address, {village}, Erode, Tamil Nadu",
                            **_source(),
                        )
                        s.add(b)

                # Markets
                if village in DEMO_MARKETS:
                    mlat, mlon = DEMO_MARKETS[village]
                    if not s.execute(select(InfrastructurePoint).where(
                            InfrastructurePoint.kind == "market",
                            InfrastructurePoint.name == f"{village} Market")).scalars().first():
                        s.add(InfrastructurePoint(
                            kind="market", name=f"{village} Market",
                            latitude=mlat, longitude=mlon,
                            is_demo=True, source_type="demo", confidence="low",
                        ))
                # transport
                if not s.execute(select(InfrastructurePoint).where(
                        InfrastructurePoint.kind == "transport",
                        InfrastructurePoint.name == f"{village} Bus Stop")).scalars().first():
                    s.add(InfrastructurePoint(
                        kind="transport", name=f"{village} Bus Stop",
                        latitude=lat + 0.002, longitude=lon + 0.001,
                        is_demo=True, source_type="demo", confidence="low",
                    ))
    print("Demo Erode data seeded (is_demo=True).")


if __name__ == "__main__":
    seed_demo()
