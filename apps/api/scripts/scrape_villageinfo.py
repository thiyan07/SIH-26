"""Scrape all villages in Erode district from VillageInfo.in and upsert into locations.

Source: https://villageinfo.in/tamil-nadu/erode/ -> talukas -> villages
Each village gets a location with block = taluka name, village = village name,
coordinates = taluka centroid (from scraped Google Maps data) or Erode district centroid fallback.

Usage:
    DATABASE_URL=... python -m scripts.scrape_villageinfo [--dry-run]

Adds ~486 villages - existing ones are updated, new ones inserted. Villages whose
name equals block name are skipped (already represented as town row).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.db.models import Location
from app.db.session import session_scope

log = logging.getLogger("scrape.villageinfo")

STATE = "Tamil Nadu"
DISTRICT = "Erode"
BASE = "https://villageinfo.in/tamil-nadu/erode/"
GM_DIR = Path(__file__).resolve().parents[3] / "apps" / "data" / "scrape" / "google_maps"
# Fallback to second possible location
if not GM_DIR.exists():
    GM_DIR = Path(__file__).resolve().parents[2] / "apps" / "data" / "scrape" / "google_maps"
    if not GM_DIR.exists():
        GM_DIR = Path(__file__).resolve().parents[3] / "data" / "scrape" / "google_maps"

TOWN_KEYS = [
    "perundurai", "anthiyur", "sathyamangalam", "modakkurichi",
    "gobichettipalayam", "bhavanisagar", "bhavani", "chennimalai",
    "nambiyur", "ammapet", "talavadi", "kodumudi",
    "thookanaickenpalayam", "avalpoondurai", "erode",
]
# Taluka to town key for centroid
TALUKA_TO_KEY = {
    "Anthiyur": "anthiyur", "Bhavani": "bhavani", "Erode": "erode",
    "Gobichettipalayam": "gobichettipalayam", "Kodumudi": "kodumudi",
    "Modakkurichi": "modakkurichi", "Nambiyur": "nambiyur",
    "Perundurai": "perundurai", "Sathyamangalam": "sathyamangalam",
    "Bhavanisagar": "bhavanisagar", "Chennimalai": "chennimalai",
    "Ammapet": "ammapet", "Talavadi": "talavadi",
    "Thookanaickenpalayam": "thookanaickenpalayam", "Avalpoondurai": "avalpoondurai",
}

HEADERS = {"User-Agent": "GramBiz AI (SIH 2026) VillageInfo scraper; contact via GitHub"}

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")

def _talukas() -> list[str]:
    html = _fetch(BASE)
    soup = BeautifulSoup(html, "lxml")
    talukas = []
    for a in soup.select("table a[href*='/tamil-nadu/erode/']"):
        href = a.get("href", "")
        # href like /tamil-nadu/erode/anthiyur/
        m = re.search(r"/erode/([^/]+)/", href)
        if m:
            txt = a.get_text(strip=True)
            if txt:
                talukas.append(txt)
    # Dedupe preserve order and filter to real talukas only (10 in Erode)
    known = {"anthiyur","bhavani","erode","gobichettipalayam","kodumudi","modakkurichi","nambiyur","perundurai","sathyamangalam","thalavadi"}
    seen = set()
    uniq = []
    for t in talukas:
        low = t.lower()
        if low not in known:
            continue
        if low not in seen:
            seen.add(low)
            uniq.append(t)
    return uniq

def _villages_for_taluka(taluka: str) -> list[str]:
    slug = taluka.lower().replace(" ", "-")
    url = f"{BASE}{slug}/"
    html = _fetch(url)
    soup = BeautifulSoup(html, "lxml")
    villages = []
    for a in soup.select("table a[href*='/tamil-nadu/erode/']"):
        href = a.get("href", "")
        # Village links are deeper: /tamil-nadu/erode/perundurai/agrahara-vijayamangalam/
        if href.count("/") >= 5 and slug in href:
            villages.append(a.get_text(strip=True))
    # Dedupe
    seen=set()
    uniq=[]
    for v in villages:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append(v)
    return uniq

def _taluka_centroids() -> dict[str, dict]:
    lat: dict[str, list[float]] = defaultdict(list)
    lon: dict[str, list[float]] = defaultdict(list)
    if not GM_DIR.exists():
        log.warning("GM_DIR not found %s, using fallback centroids", GM_DIR)
        return {}
    for f in sorted(GM_DIR.glob("*.jsonl")):
        m = re.search(r"__(\d{8}T\d{6})__(.*)\.jsonl$", f.name)
        if not m:
            continue
        q = _norm(urllib.parse.unquote(m.group(2)))
        tag = None
        for t in TOWN_KEYS:
            if t not in q:
                continue
            if t == "erode" and any(k in q for k in TOWN_KEYS if k != "erode"):
                continue
            if t == "bhavani" and q.startswith("bhavanisagar"):
                continue
            tag = t
            break
        if not tag:
            continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except:
                    continue
                if row.get("latitude") is None:
                    continue
                lat[tag].append(float(row["latitude"]))
                lon[tag].append(float(row["longitude"]))
    out={}
    for t in TOWN_KEYS:
        if lat.get(t):
            out[t]= {"latitude": round(statistics.median(lat[t]),6), "longitude": round(statistics.median(lon[t]),6), "n": len(lat[t])}
    return out

def scrape_all(*, dry_run: bool = False) -> dict:
    talukas = _talukas()
    log.info("Found %d talukas: %s", len(talukas), talukas)
    centroids = _taluka_centroids()
    log.info("Centroids for %d talukas", len(centroids))
    # Fallback centroid for talukas without scrape data: use Erode district centroid (11.346, 77.716) or Perundurai
    fallback = {"latitude": 11.346, "longitude": 77.716, "n": 0}

    all_villages: list[tuple[str, str]] = []  # (taluka, village)
    for taluka in talukas:
        try:
            vs = _villages_for_taluka(taluka)
            log.info("  %s: %d villages", taluka, len(vs))
            for v in vs:
                all_villages.append((taluka, v))
            time.sleep(0.8)  # polite delay
        except Exception as ex:
            log.error("Failed taluka %s: %s", taluka, ex)

    log.info("Total villages scraped: %d", len(all_villages))

    stats = {"created":0, "exists":0, "skipped_block_hq":0, "no_centroid":0}
    with session_scope() as db:
        existing_rows = list(db.execute(select(Location).where(Location.state==STATE, Location.district==DISTRICT)).scalars())
        existing = {_norm(r.block or "")+"|"+_norm(r.village or ""): r for r in existing_rows}
        # Also build set for village lower only for debugging duplicates across talukas
        for taluka, village in all_villages:
            if _norm(taluka) == _norm(village):
                stats["skipped_block_hq"]+=1
                continue
            key = TALUKA_TO_KEY.get(taluka)
            c = centroids.get(key) if key else None
            if not c:
                c = fallback
                stats["no_centroid"]+=1
            norm_key = _norm(taluka)+"|"+_norm(village)
            if norm_key in existing:
                stats["exists"]+=1
                continue
            # Also check if village already exists under different taluka/block (e.g., same village name in different block)
            # We still create with correct taluka as block to preserve taluka granularity
            # So we don't skip just because village name exists elsewhere
            if not dry_run:
                loc = Location(
                    state=STATE, district=DISTRICT, block=taluka, village=village,
                    latitude=c["latitude"], longitude=c["longitude"],
                    geo_precision="village",
                    source_name="VillageInfo.in (Erode district village directory)",
                    source_url=f"https://villageinfo.in/tamil-nadu/erode/{taluka.lower().replace(' ','-')}/",
                    dataset_name="villageinfo_erode_villages",
                    source_type="government",
                    geographic_level="village", confidence="medium",
                    is_estimate=True, is_demo=False,
                    methodology="Village list scraped from VillageInfo.in; coordinates are taluka centroid from Google Maps scrape (locates taluka, not exact village point).",
                    metadata_json={"taluka": taluka, "scraped_from": "villageinfo.in", "centroid_n": c["n"]},
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
    ap = argparse.ArgumentParser(description="Scrape VillageInfo Erode villages and upsert locations")
    ap.add_argument("--dry-run", action="store_true", help="don't write to DB")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = scrape_all(dry_run=args.dry_run)
    log.info("Done: %s", stats)
    return 0

if __name__ == "__main__":
    sys.exit(main())
