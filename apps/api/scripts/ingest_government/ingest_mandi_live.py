"""Ingest live, dated mandi (APMC) prices for Erode district from the ACROP
public market page (a free, keyless web page mirroring daily APMC/Agmarknet
data via the data.gov.in pipeline).

Why this source: the official agmarknet.gov.in API is auth-token gated and
agmarknet.nic.in / the CEDA mirror are unreachable; data.gov.in resource
downloads require a free API key.  ACROP publishes the same APMC-reported
daily tables on public pages (``/prices/<commodity>/tamil-nadu/erode``)
server-rendered with per-market Modal/Min/Max prices and a reference date.
This script extracts those tables verbatim into ``market_prices`` rows with
provenance flagged as an aggregator mirror (confidence=medium) - never
fabricating values.

Data model (per market_prices row):
  item_name   -> human commodity label
  market_name -> APMC / Uzhavar Sandhai market as shown on the source page
  modal/min/max_price -> reported wholesale prices (₹)
  unit        -> unit token read from the source page (qtl = quintal)
  reference_date -> the date ACROP published for that market row

Usage:
  python -m scripts.ingest_government.ingest_mandi_live
  python -m scripts.ingest_government.ingest_mandi_live --limit 5
  python -m scripts.ingest_government.ingest_mandi_live --commodities onion turmeric
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

from app.db.models import DataSnapshot, MarketPrice
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_mandi_live")

BASE = "https://acrop.app"
ERODE = f"{BASE}/prices/%s/tamil-nadu/erode"
SOURCE_NAME = "ACROP Mandi (APMC/Agmarknet via data.gov.in, daily tables)"
SOURCE_URL = f"{BASE}/mandi/tamil-nadu/erode"
DATASET_NAME = "ACROP Erode market prices (daily APMC tables)"
UA = "GramBizAI/1.0 (erode mandi ingest; public keyless page)"

COMMODITIES = {
    "turmeric": "Turmeric",
    "paddy": "Paddy (Rice)",
    "maize": "Maize",
    "potato": "Potato",
    "onion": "Onion",
    "tomato": "Tomato",
    "greenchilli": "Green Chilli",
    "groundnut": "Groundnut",
    "banana": "Banana",
    "coconut": "Coconut",
    "ginger": "Ginger",
    "corianderleaf": "Coriander (Leaf)",
    "greenpeasdry": "Green Peas (Dry)",
    "brinjal": "Brinjal",
    "cabbage": "Cabbage",
    "beans": "Beans (Vegetable)",
    "okra": "Okra",
    "carrot": "Carrot",
    "cauliflower": "Cauliflower",
    "beetroot": "Beetroot",
    "cucumber": "Cucumber",
    "cowpeaveg": "Cowpea (Vegetable)",
    "amaranthus": "Amaranthus",
    "drumstick": "Drumstick",
    "mango": "Mango",
}


def _strip_tags(s: str) -> str:
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("\xa0", " ").strip()


def _parse_rupee(s: str):
    s = _strip_tags(s)
    m = re.search(r"[\d,]+(?:\.\d+)?", s or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_date(s: str) -> datetime.date | None:
    s = _strip_tags(s)
    try:
        return datetime.strptime(s, "%d %b %Y").date()
    except ValueError:
        try:
            return datetime.strptime(s, "%d %b %Y IST").date()
        except ValueError:
            return None


def _page_unit(html: str) -> str:
    low = html.lower()
    if re.search(r"quintal|qtl", low):
        return "quintal"
    if re.search(r"per\s*kg\b|/kg\b|per\s*kilogram", low):
        return "kg"
    if re.search(r"per\s*tonne?\b|tonne?", low):
        return "tonne"
    return "quintal"


def fetch_market_rows(slug: str, base: str = ERODE) -> tuple[list[dict], str]:
    """Return list of market rows and the reference-unit token for a commodity."""
    url = base % slug
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - public page
        html = resp.read().decode("utf-8", "replace")
    unit = _page_unit(html)
    rows: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        if "₹" not in tr:
            continue
        cells = [_strip_tags(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        if len(cells) < 5:
            continue
        market, modal, lo, hi, date_txt = cells[:5]
        date = _parse_date(date_txt)
        if not market or not date:
            continue
        rows.append({
            "market": market,
            "modal": _parse_rupee(modal),
            "min": _parse_rupee(lo),
            "max": _parse_rupee(hi),
            "date": date,
        })
    return rows, unit


def upsert_price(session, item_name, market, date, modal, lo, hi, unit, source_url, snapshot):
    existing = session.query(MarketPrice).filter(
        MarketPrice.item_name == item_name,
        MarketPrice.market_name == market,
        MarketPrice.reference_date == date,
    ).first()
    if existing:
        existing.modal_price = modal
        existing.min_price = lo
        existing.max_price = hi
        existing.unit = unit
        return
    session.add(MarketPrice(
        item_name=item_name, category="agriculture",
        unit=unit, min_price=lo, max_price=hi, modal_price=modal,
        market_name=market, state="Tamil Nadu", district="Erode", mandi=market,
        source_name=SOURCE_NAME, source_url=source_url,
        dataset_name=DATASET_NAME, source_type="market_prices",
        reference_date=date, reference_year=date.year,
        retrieved_at=datetime.now(timezone.utc),
        geographic_level="market",
        confidence="medium",
        completeness=0.7,  # modal/min/max from a public mirror, no arrival qty here
        methodology="Daily APMC/Agmarknet table published on the public ACROP "
                    "page (keyless, server-rendered). Parsed verbatim: market "
                    "name, modal/min/max price, unit token and reference date "
                    "as shown. Aggregator mirror of ministry/APMC-reported "
                    "data, not a direct ministry API.",
        is_estimate=False,
        is_demo=False,
    ))
    snapshot.records_ingested += 1


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="only harvest the first N commodities (debug)")
    ap.add_argument("--commodities", nargs="*", default=None,
                    help="specific commodity slugs to harvest")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    selected = {c: COMMODITIES[c] for c in args.commodities} if args.commodities else dict(COMMODITIES)
    if args.limit:
        selected = dict(list(selected.items())[:args.limit])
    if not selected:
        log.error("no commodities to harvest")
        return 1

    snapshot = DataSnapshot(job_name="market_prices_live_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(s, "market_prices_live", "Live mandi prices (ACROP mirror)",
                             "prices", "market_prices",
                             "Daily APMC/Agmarknet tables for Erode from a public "
                             "keyless mirror; refresh daily.")
        for slug, label in selected.items():
            rows, unit = fetch_market_rows(slug)
            if not rows:
                log.warning("  %-16s no market rows", label)
                continue
            for r in rows:
                upsert_price(s, label, r["market"], r["date"], r["modal"],
                             r["min"], r["max"], unit, ERODE % slug, snapshot)
            log.info("%-16s %d market(s), unit=%s, ref %s",
                     label, len(rows), unit, rows[0]["date"])
            time.sleep(0.35)  # be polite to the public page
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    log_event("ingest", job="market_prices_live_erode",
              commodities=len(selected), records=snapshot.records_ingested,
              status="completed")
    log.info("market price rows written: %d", snapshot.records_ingested)
    return 0


if __name__ == "__main__":
    sys.exit(main())
