"""Scrape VillageInfo for districts near Erode and upsert as locations.

Districts: Coimbatore, Tiruppur, Namakkal, Salem (in order)
Each district's villages are scraped from VillageInfo.in/taluka pages,
with fallback coordinates per district.

Usage:
    DATABASE_URL=... python -m scripts.scrape_nearby_districts --district Coimbatore --dry-run
    DATABASE_URL=... python -m scripts.scrape_nearby_districts --all --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.db.models import Location
from app.db.session import session_scope

import logging
log = logging.getLogger("scrape.nearby")

STATE = "Tamil Nadu"
BASE_TMPL = "https://villageinfo.in/tamil-nadu/{district}/"
# District slug mapping for VillageInfo URLs (some have special slugs)
DISTRICT_SLUGS = {
    "The Nilgiris": "the-nilgiris",
    "Nilgiris": "the-nilgiris",
    "Viluppuram": "viluppuram",
    "Villupuram": "viluppuram",
}

# Fallback centroids per district (approx district HQ) - 15 districts total
FALLBACKS = {
    "Coimbatore": (11.0168, 76.9558),
    "Tiruppur": (11.1085, 77.3411),
    "Namakkal": (11.2189, 78.1670),
    "Salem": (11.6643, 78.1460),
    "Erode": (11.346, 77.716),
    "Karur": (10.9601, 78.0766),
    "The Nilgiris": (11.4102, 76.6950),
    "Nilgiris": (11.4102, 76.6950),
    "Dindigul": (10.3673, 77.9803),
    "Tiruchirappalli": (10.7905, 78.7047),
    "Dharmapuri": (12.1278, 78.1582),
    "Krishnagiri": (12.5186, 78.2140),
    "Theni": (10.0104, 77.4768),
    "Pudukkottai": (10.3803, 78.8208),
    "Thanjavur": (10.7870, 79.1378),
    "Viluppuram": (11.9401, 79.4861),
    "Villupuram": (11.9401, 79.4861),
}
ALL_NEARBY = ["Coimbatore", "Tiruppur", "Namakkal", "Salem", "Karur", "The Nilgiris", "Dindigul", "Tiruchirappalli", "Dharmapuri", "Krishnagiri", "Theni", "Pudukkottai", "Thanjavur", "Viluppuram"]

HEADERS = {"User-Agent": "GramBiz AI (SIH 2026) VillageInfo scraper"}

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")

def _talukas(district: str) -> list[str]:
    slug = DISTRICT_SLUGS.get(district, district.lower())
    url = BASE_TMPL.format(district=slug)
    html = _fetch(url)
    soup = BeautifulSoup(html, "lxml")
    talukas = []
    for a in soup.select("table a[href*='/tamil-nadu/']"):
        href = a.get("href", "")
        # href like /tamil-nadu/coimbatore/sulur/
        m = re.search(rf"/{slug}/([^/]+)/", href, re.IGNORECASE)
        if m:
            txt = a.get_text(strip=True)
            if txt and txt.lower() not in ("coimbatore", district.lower(), slug):
                talukas.append(txt)
    # Dedupe and filter to plausible taluka names (capitalized, not too long)
    seen=set()
    uniq=[]
    for t in talukas:
        low=t.lower()
        if low in ("list of development blocks in "+district.lower(), "list of block panchayats in "+district.lower(), "list of gram panchayats in "+district.lower()):
            continue
        if low not in seen:
            seen.add(low)
            uniq.append(t)
    # The page's first table is talukas, second is maybe not. We need to limit to known count
    # For safety, fetch the taluka list via the specific heading
    # If we got too many, trim to those that appear in the taluka table
    return uniq[:20]

def _villages_for_taluka(district: str, taluka: str) -> list[str]:
    slug = taluka.lower().replace(" ", "-")
    dslug = DISTRICT_SLUGS.get(district, district.lower())
    url = f"{BASE_TMPL.format(district=dslug)}{slug}/"
    html = _fetch(url)
    soup = BeautifulSoup(html, "lxml")
    villages = []
    for a in soup.select("table a[href*='/tamil-nadu/']"):
        href = a.get("href", "")
        if f"/{dslug}/{slug}/" in href.lower() and href.count("/") >= 5:
            villages.append(a.get_text(strip=True))
    seen=set()
    uniq=[]
    for v in villages:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append(v)
    return uniq

def scrape_district(district: str, *, dry_run: bool = False) -> dict:
    talukas = _talukas(district)
    log.info("District %s: %d talukas %s", district, len(talukas), talukas)
    fallback_lat, fallback_lon = FALLBACKS.get(district, (11.3, 77.7))
    stats = {"district": district, "talukas": len(talukas), "villages_scraped": 0, "created": 0, "exists": 0}
    all_villages: list[tuple[str, str]] = []
    for taluka in talukas:
        try:
            vs = _villages_for_taluka(district, taluka)
            log.info("  %s: %d villages", taluka, len(vs))
            for v in vs:
                all_villages.append((taluka, v))
            time.sleep(0.7)
        except Exception as ex:
            log.error("  %s failed: %s", taluka, ex)
    stats["villages_scraped"] = len(all_villages)
    # Upsert
    with session_scope() as db:
        existing_rows = list(db.execute(select(Location).where(Location.state==STATE, Location.district==district)).scalars())
        existing = {_norm(r.block or "")+"|"+_norm(r.village or ""): r for r in existing_rows}
        for taluka, village in all_villages:
            if _norm(taluka) == _norm(village):
                continue
            key = _norm(taluka)+"|"+_norm(village)
            if key in existing:
                stats["exists"]+=1
                continue
            dslug = DISTRICT_SLUGS.get(district, district.lower())
            if not dry_run:
                loc = Location(
                    state=STATE, district=district, block=taluka, village=village,
                    latitude=fallback_lat, longitude=fallback_lon,
                    geo_precision="village",
                    source_name="VillageInfo.in (district village directory)",
                    source_url=f"https://villageinfo.in/tamil-nadu/{dslug}/{taluka.lower().replace(' ','-')}/",
                    dataset_name=f"villageinfo_{district.lower()}_villages",
                    source_type="government",
                    geographic_level="village", confidence="medium",
                    is_estimate=True, is_demo=False,
                    methodology="Village list scraped from VillageInfo.in; coordinates are district fallback (not exact village point).",
                    metadata_json={"district": district, "taluka": taluka, "scraped_from": "villageinfo.in"},
                    retrieved_at=dt.datetime.now(dt.timezone.utc),
                )
                db.add(loc)
            stats["created"]+=1
        if not dry_run:
            db.commit()
        else:
            db.rollback()
    return stats

def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    import argparse
    ap = argparse.ArgumentParser(description="Scrape nearby districts villages")
    ap.add_argument("--district", help="Single district e.g. Coimbatore")
    ap.add_argument("--all", action="store_true", help="All nearby districts")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    districts = ALL_NEARBY if args.all else ([args.district] if args.district else ALL_NEARBY[:1])
    for d in districts:
        stats = scrape_district(d, dry_run=args.dry_run)
        log.info("Done %s: %s", d, stats)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
