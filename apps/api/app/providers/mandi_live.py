"""Live mandi price provider — best-effort scrape for districts without DB prices.

Uses the same ACROP public mirror as the batch ingest (keyless, server-rendered
APMC tables) but generalized beyond Erode: fetches ``/prices/<commodity>/tamil-nadu/<district-slug>``
for a curated commodity list.

This is a *fallback* only: when DB has no verified prices for the district,
the analysis pipeline tries this provider with a short timeout (4s). Failure
never blocks analysis — it simply returns no live rows and the caller reports
UNAVAILABLE with reduced confidence.

No prices are fabricated: rows are only emitted when the remote page actually
returns a server-rendered table with market/modal/min/max/date.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime
from typing import Optional

BASE = "https://acrop.app"
UA = "GramBizAI/1.0 (live mandi fallback; public keyless page)"

# Tamil Nadu district slugs as used by ACROP URLs (lowercase, hyphenated)
TN_DISTRICT_SLUGS = {
    "erode": "erode", "coimbatore": "coimbatore", "salem": "salem",
    "madurai": "madurai", "tiruchirappalli": "tiruchirappalli",
    "tiruppur": "tiruppur", "namakkal": "namakkal", "dindigul": "dindigul",
    "thanjavur": "thanjavur", "tirunelveli": "tirunelveli",
    "vellore": "vellore", "kanchipuram": "kanchipuram", "thoothukudi": "thoothukudi",
    "karur": "karur", "dharmapuri": "dharmapuri", "krishnagiri": "krishnagiri",
    "cuddalore": "cuddalore", "nagapattinam": "nagapattinam", "theni": "theni",
    "tiruvannamalai": "tiruvannamalai", "villupuram": "villupuram",
    "pudukkottai": "pudukkottai", "ramanathapuram": "ramanathapuram",
    "sivaganga": "sivaganga", "nilgiris": "nilgiris", "nilgiri": "nilgiris",
    "kanyakumari": "kanyakumari", "ariyalur": "ariyalur", "perambalur": "perambalur",
    "tirupathur": "tirupathur", "ranipet": "ranipet", "chengalpattu": "chengalpattu",
    "kallakurichi": "kallakurichi", "tenkasi": "tenkasi", "mayiladuthurai": "mayiladuthurai",
    "chennai": "chennai", "tiruvallur": "tiruvallur",
}

# Core commodities to try (matches RELEVANT_ITEMS intersections)
COMMODITY_SLUGS = {
    "paddy": "Paddy (Rice)", "maize": "Maize", "potato": "Potato",
    "onion": "Onion", "tomato": "Tomato", "groundnut": "Groundnut",
    "banana": "Banana", "coconut": "Coconut", "turmeric": "Turmeric",
    "cotton": "Cotton", "sugarcane": "Sugarcane", "milk": "Milk",
}


def _slug_for_district(district: str) -> Optional[str]:
    return TN_DISTRICT_SLUGS.get(district.strip().lower())


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


def _parse_date(s: str):
    s = _strip_tags(s)
    for fmt in ("%d %b %Y", "%d %b %Y IST", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _page_unit(html: str) -> str:
    low = html.lower()
    if re.search(r"quintal|qtl", low):
        return "quintal"
    if re.search(r"per\s*kg\b|/kg\b", low):
        return "kg"
    return "quintal"


def _fetch_commodity_for_district(slug: str, district_slug: str, timeout_s: int = 4) -> list[dict]:
    url = f"{BASE}/prices/{slug}/tamil-nadu/{district_slug}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            html = resp.read().decode("utf-8", "replace")
    except Exception:
        return []
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
            "item_name": COMMODITY_SLUGS.get(slug, slug.title()),
            "market_name": market,
            "modal_price": _parse_rupee(modal),
            "min_price": _parse_rupee(lo),
            "max_price": _parse_rupee(hi),
            "reference_date": date,
            "unit": unit,
        })
    return rows


def fetch_live_prices_for_district(district: str, timeout_s: int = 4, max_commodities: int = 6) -> list[dict]:
    """Fetch live mandi rows for a Tamil Nadu district via ACROP mirror.

    Tries up to max_commodities commodity pages in order; stops after 2
    successful commodity fetches (enough to produce evidence) to stay fast.
    Total wall time is bounded by per-page timeout × commodities tried.

    Returns list of normalized row dicts (item_name, market_name, modal_price,
    min_price, max_price, reference_date, unit). Empty list on any failure.
    """
    district_slug = _slug_for_district(district)
    if not district_slug:
        return []
    # Non-Erode districts: ACROP may not have pages; try a small set and bail fast
    out: list[dict] = []
    tried = 0
    successes = 0
    for slug in list(COMMODITY_SLUGS.keys())[:max_commodities]:
        tried += 1
        rows = _fetch_commodity_for_district(slug, district_slug, timeout_s=timeout_s)
        if rows:
            out.extend(rows)
            successes += 1
            if successes >= 2:
                break
        # brief politeness delay only between commodities
        if tried < max_commodities and successes < 2:
            time.sleep(0.15)
        if successes >= 2:
            break
    return out
