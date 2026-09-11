"""Mandibhavindia provider — district-level mandi price scrape (Tier 4 secondary).

Scrapes https://mandibhavindia.in/en/mandi/tamil-nadu/<district> pages which
are server-rendered Next.js with tables: Commodity | Market | Variety | Min | Max | Modal | Date.
Same underlying Agmarknet/eNAM daily data as ACROP, but covers 385 mandis across 37 districts.

This is Tier 4 secondary (explicitly labelled), never silent override of Tier 1 official.
Up-to-date: latest report 2026-09-11, 81 commodities, 11,351 prices.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime

BASE = "https://mandibhavindia.in/en/mandi/tamil-nadu"
UA = "GramBizAI/1.0 (mandibhavindia district scrape; secondary fallback)"
DISTRICT_SLUGS = {
    "Ariyalur": "ariyalur", "Chengalpattu": "chengalpattu", "Chennai": "chennai",
    "Coimbatore": "coimbatore", "Cuddalore": "cuddalore", "Dharmapuri": "dharmapuri",
    "Dindigul": "dindigul", "Erode": "erode", "Kallakurichi": "kallakurichi",
    "Kanchipuram": "kancheepuram", "Kanniyakumari": "kanyakumari", "Karur": "karur",
    "Krishnagiri": "krishnagiri", "Madurai": "madurai", "Mayiladuthurai": "mayiladuthurai",
    "Nagapattinam": "nagapattinam", "Namakkal": "namakkal", "Perambalur": "perambalur",
    "Pudukkottai": "pudukkottai", "Ramanathapuram": "ramanathapuram", "Ranipet": "ranipet",
    "Salem": "salem", "Sivaganga": "sivaganga", "Tenkasi": "tenkasi", "Thanjavur": "thanjavur",
    "The Nilgiris": "nilgiris", "Theni": "theni", "Thiruvallur": "thiruvallur",
    "Thiruvarur": "thiruvarur", "Thoothukudi": "thoothukudi-(tuticorin)", "Tuticorin": "thoothukudi-(tuticorin)",
    "Tiruchirappalli": "tiruchirappalli", "Tirunelveli": "tirunelveli", "Tirupathur": "tirupathur",
    "Tiruppur": "tiruppur", "Tiruvannamalai": "tiruvannamalai", "Vellore": "vellore",
    "Villupuram": "viluppuram", "Viluppuram": "viluppuram", "Virudhunagar": "virudhunagar",
}

def _strip(s: str) -> str:
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("\xa0", " ").strip()

def _parse_rupee(s: str):
    m = re.search(r"[\d,]+", s or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None

def _parse_date(s: str):
    s = _strip(s)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None

def fetch_district_prices(district: str, timeout_s: int = 12) -> list[dict]:
    slug = DISTRICT_SLUGS.get(district) or DISTRICT_SLUGS.get(district.title()) or district.lower().replace(" ", "-")
    url = f"{BASE}/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - public mandi page
        html = resp.read().decode("utf-8", "replace")
    rows: list[dict] = []
    # Table rows: <tr> with 7 tds: Commodity | Market | Variety | Min | Max | Modal | Date
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        if "₹" not in tr and "Modal" not in tr:
            # also check if row has price numbers
            if not re.search(r"\d{3,}", tr):
                continue
        cells = [_strip(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) < 6:
            continue
        # Header row check
        if cells[0].lower() == "commodity" or cells[1].lower() == "market":
            continue
        # Cells: 0 Commodity, 1 Market, 2 Variety, 3 Min, 4 Max, 5 Modal, 6 Date
        commodity = cells[0] if len(cells) > 0 else ""
        market = cells[1] if len(cells) > 1 else ""
        variety = cells[2] if len(cells) > 2 else ""
        min_p = _parse_rupee(cells[3]) if len(cells) > 3 else None
        max_p = _parse_rupee(cells[4]) if len(cells) > 4 else None
        modal_p = _parse_rupee(cells[5]) if len(cells) > 5 else None
        date_txt = cells[6] if len(cells) > 6 else ""
        ref_date = _parse_date(date_txt)
        if not commodity or not market or modal_p is None:
            continue
        # Filter to recent (last 30 days) to stay up-to-date
        # But keep all for now, confidence will handle staleness
        rows.append({
            "item_name": commodity,
            "market_name": market,
            "variety": variety,
            "min_price": min_p,
            "max_price": max_p,
            "modal_price": modal_p,
            "reference_date": ref_date,
            "unit": "quintal",
            "source": "mandibhavindia",
        })
    return rows

def fetch_live_prices_for_district(district: str, timeout_s: int = 12, max_rows: int = 100) -> list[dict]:
    try:
        rows = fetch_district_prices(district, timeout_s=timeout_s)
        time.sleep(0.3)
        return rows[:max_rows]
    except Exception:
        return []
