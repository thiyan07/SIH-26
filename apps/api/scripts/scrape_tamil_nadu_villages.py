"""Scrape all Tamil Nadu villages from VillageInfo.in for 38 districts.

Uses taluka centroids from Google Maps scrape where available, otherwise district fallback.
Writes to locations with source_name='VillageInfo.in (Tamil Nadu directory)' and marks is_estimate=True.

Usage:
  DATABASE_URL=... .venv/bin/python -m scripts.scrape_tamil_nadu_villages [--dry-run] [--district Erode]
"""
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

log = logging.getLogger("scrape.tn_villageinfo")

# 38 Tamil Nadu districts from Bharat Atlas lgd_districts where stname=TAMIL NADU
DISTRICTS = [
    "Ariyalur","Chengalpattu","Chennai","Coimbatore","Cuddalore","Dharmapuri","Dindigul",
    "Erode","Kallakurichi","Kanchipuram","Kanniyakumari","Karur","Krishnagiri","Madurai",
    "Mayiladuthurai","Nagapattinam","Namakkal","Perambalur","Pudukkottai","Ramanathapuram",
    "Ranipet","Salem","Sivaganga","Tenkasi","Thanjavur","The Nilgiris","Theni","Thiruvallur",
    "Thiruvarur","Thoothukudi","Tiruchirappalli","Tirunelveli","Tirupathur","Tiruppur",
    "Tiruvannamalai","Vellore","Villupuram","Virudhunagar",
]
# Map district name to VillageInfo slug (lowercase, hyphen)
# Special cases: Tuticorin -> thoothukudi, Tenkasi etc already correct
SLUG_MAP = {
    "Thoothukudi": "thoothukudi",
    "The Nilgiris": "the-nilgiris",
    "Tiruchirappalli": "tiruchirappalli",
    "Tirunelveli": "tirunelveli",
}

BASE_TMPL = "https://villageinfo.in/tamil-nadu/{slug}/"

HEADERS = {"User-Agent": "GramBiz AI (SIH 2026) TN VillageInfo scraper; contact via GitHub"}

# Fallback coordinates per district (approx centroid) – used if no taluka centroid
DISTRICT_FALLBACK = {
    "Erode": (11.346, 77.716),
    "Coimbatore": (11.016, 76.955),
    "Tiruppur": (11.108, 77.341),
    "Salem": (11.664, 78.146),
}

def slug_for(district: str) -> str:
    if district in SLUG_MAP:
        return SLUG_MAP[district]
    return district.lower().replace(" ", "-")

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")

def talukas_for(district: str) -> list[str]:
    slug = slug_for(district)
    url = BASE_TMPL.format(slug=slug)
    try:
        html = fetch(url)
    except Exception as ex:
        log.warning("Failed district %s: %s", district, ex)
        return []
    soup = BeautifulSoup(html, "lxml")
    talukas = []
    for a in soup.select("table a[href*='/tamil-nadu/']"):
        href = a.get("href", "")
        if f"/{slug}/" not in href.lower():
            continue
        parts = [p for p in href.strip("/").split("/") if p]
        if len(parts) == 3:  # tamil-nadu / district / taluka
            txt = a.get_text(strip=True)
            if not txt or txt.lower() == district.lower():
                continue
            low = txt.lower()
            if "list of" in low or "blocks" in low or "panchayats" in low:
                continue
            if len(txt) > 35:
                continue
            talukas.append(txt)
    # dedupe preserve order
    seen=set(); uniq=[]
    for t in talukas:
        low=t.lower()
        if low not in seen:
            seen.add(low)
            uniq.append(t)
    return uniq

def villages_for(district: str, taluka: str) -> list[str]:
    dslug = slug_for(district)
    tslug = taluka.lower().replace(" ", "-")
    url = f"https://villageinfo.in/tamil-nadu/{dslug}/{tslug}/"
    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")
    villages=[]
    for a in soup.select("table a[href*='/tamil-nadu/']"):
        href=a.get("href","")
        if f"/{dslug}/{tslug}/" not in href.lower():
            continue
        parts=[p for p in href.strip("/").split("/") if p]
        if len(parts)==4:  # village level
            villages.append(a.get_text(strip=True))
    seen=set(); uniq=[]
    for v in villages:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append(v)
    return uniq

def taluka_centroids() -> dict[str, dict]:
    # reuse Google Maps scrape if exists – same as Erode script
    for p in [Path(__file__).resolve().parents[2]/"data"/"scrape"/"google_maps", Path(__file__).resolve().parents[3]/"data"/"scrape"/"google_maps"]:
        if p.exists():
            gm_dir=p
            break
    else:
        return {}
    lat=defaultdict(list); lon=defaultdict(list)
    for f in sorted(gm_dir.glob("*.jsonl")):
        m=re.search(r"__(\d{8}T\d{6})__(.*)\.jsonl$", f.name)
        if not m: continue
        q=re.sub(r"[^a-z0-9]","", urllib.parse.unquote(m.group(2)).lower())
        tag=None
        for t in ["perundurai","anthiyur","sathyamangalam","modakkurichi","gobichettipalayam","bhavanisagar","bhavani","chennimalai","nambiyur","ammapet","talavadi","kodumudi","thookanaickenpalayam","avalpoondurai","erode"]:
            if t in q:
                tag=t; break
        if not tag: continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row=json.loads(line)
                except: continue
                if row.get("latitude") is None: continue
                lat[tag].append(float(row["latitude"])); lon[tag].append(float(row["longitude"]))
    out={}
    for t in lat:
        if lat[t]:
            out[t]={"latitude": round(statistics.median(lat[t]),6), "longitude": round(statistics.median(lon[t]),6), "n": len(lat[t])}
    return out

def scrape_all(district_filter=None, dry_run=False):
    centroids=taluka_centroids()
    fallback_erode=(11.346,77.716)
    stats={"created":0,"exists":0,"skipped":0,"districts":0,"talukas":0,"villages_scraped":0}
    districts = [district_filter] if district_filter else DISTRICTS
    with session_scope() as db:
        existing=list(db.execute(select(Location)).scalars())
        existing_keys={ ( (r.state or "").lower(), (r.district or "").lower(), (r.block or "").lower(), (r.village or "").lower() ): r for r in existing}
        for district in districts:
            log.info("District %s", district)
            talukas=talukas_for(district)
            if not talukas:
                log.warning("  no talukas found for %s", district)
                continue
            stats["districts"]+=1; stats["talukas"]+=len(talukas)
            log.info("  %d talukas: %s", len(talukas), talukas[:5])
            for taluka in talukas:
                try:
                    vs=villages_for(district, taluka)
                except Exception as ex:
                    log.error("  failed %s/%s: %s", district, taluka, ex)
                    time.sleep(0.5); continue
                log.info("    %s: %d villages", taluka, len(vs))
                stats["villages_scraped"]+=len(vs)
                # centroid for this taluka if available
                key=taluka.lower().replace(" ","")
                c=centroids.get(key)
                if not c:
                    # try district fallback
                    lat, lon = DISTRICT_FALLBACK.get(district, fallback_erode)
                    c={"latitude": lat, "longitude": lon, "n": 0}
                for village in vs:
                    norm=( "tamil nadu", district.lower(), taluka.lower(), village.lower())
                    if norm in existing_keys:
                        stats["exists"]+=1
                        continue
                    if taluka.lower()==village.lower():
                        stats["skipped"]+=1
                        continue
                    if not dry_run:
                        loc=Location(
                            state="Tamil Nadu", district=district, block=taluka, village=village,
                            latitude=c["latitude"], longitude=c["longitude"],
                            geo_precision="village",
                            source_name="VillageInfo.in (Tamil Nadu directory)",
                            source_url=f"https://villageinfo.in/tamil-nadu/{slug_for(district)}/{taluka.lower().replace(' ','-')}/",
                            dataset_name="villageinfo_tn_villages",
                            source_type="government",
                            geographic_level="village", confidence="medium",
                            is_estimate=True, is_demo=False,
                            methodology="Village list scraped from VillageInfo.in; coordinates are taluka centroid (or district fallback) – exact village point not in source, marked is_estimate=True.",
                            metadata_json={"district": district, "taluka": taluka, "centroid_n": c["n"]},
                            retrieved_at=dt.datetime.now(dt.timezone.utc),
                        )
                        db.add(loc)
                    stats["created"]+=1
                time.sleep(0.8)
            if not dry_run:
                db.commit()
        if dry_run:
            db.rollback()
    return stats

def main(argv=None):
    argv=argv if argv is not None else sys.argv[1:]
    ap=argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--district", help="single district to scrape")
    args=ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats=scrape_all(district_filter=args.district, dry_run=args.dry_run)
    log.info("Done: %s", stats)
    return 0

if __name__=="__main__":
    import sys; sys.exit(main())
