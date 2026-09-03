"""Scrape the complete Census 2011 village directory for Erode district.

Vill.co.in publishes a static, keyless village directory built from the
District Census Handbook (DCHB) Erode 2011.  It is grouped under the five
Erode taluks, and every taluk page lists each village in a plain HTML table
with Village Code, Population, Households, Area (ha), CD Block, and Gram
Panchayat.

This is the largest directly-scrapeable breakdown of official Census 2011
data for Erode (306 village records vs. the ~178 we had from the district
portal PDFs), and it resolves the taluk/block mismatch by carrying the CD
Block on every row.

We use "scrapling", a lightweight fetch-and-parse web scraper, so no browser
engine is required.  This is a public open-data extract; keep runs small and
politely paced.

Usage:
  python -m scripts.ingest_government.scrape_erode_villages \
      --out data/scrape/erode_villages/erode_villages.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from scrapling.fetchers import Fetcher

log = logging.getLogger("scrape_erode_villages")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
DISTRICT_URL = "https://vill.co.in/tamil-nadu/erode/"

_VILLAGE_HEADERS = {
    "Village", "Village Code", "Population", "Households",
    "Area (ha)", "CD Block", "Gram Panchayat",
}


def _num(raw: str):
    cleaned = re.sub(r"[^\d.]", "", raw or "")
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def taluk_urls(page) -> list[str]:
    """Discover the per-taluk directory URLs from the district page."""
    out = []
    seen = set()
    for a in page.css("a[href]"):
        href = a.attrib.get("href", "")
        if not href.startswith("/tamil-nadu/erode/"):
            continue
        tail = href.rsplit("/", 2)[-2] if href.rstrip("/").endswith(("/",)) else href.rsplit("/", 1)[-1]
        # taluk pages have a 6xxx census code in the slug and no second code
        if re.search(r"-\d{9}/$", href) and href not in seen:
            seen.add(href)
            out.append("https://vill.co.in" + href)
    return out


def extract_villages(taluk_page) -> list[dict]:
    rows = []
    for table in taluk_page.css("table"):
        trs = table.css("tr")
        if not trs:
            continue
        header = [c.get_all_text(" ") for c in trs[0].css("td,th")]
        if "Village" not in header or "CD Block" not in header:
            continue
        idx = {
            "village": header.index("Village"),
            "code": header.index("Village Code") if "Village Code" in header else None,
            "population": header.index("Population") if "Population" in header else None,
            "households": header.index("Households") if "Households" in header else None,
            "area": header.index("Area (ha)") if "Area (ha)" in header else None,
            "block": header.index("CD Block") if "CD Block" in header else None,
            "panchayat": header.index("Gram Panchayat") if "Gram Panchayat" in header else None,
        }
        for tr in trs[1:]:
            cells = [c.get_all_text(" ") for c in tr.css("td,th")]
            if idx["village"] >= len(cells):
                continue
            name = cells[idx["village"]].replace(".", "").strip()
            if not name or not any(ch.isalpha() for ch in name):
                continue
            block = cells[idx["block"]].strip() if idx["block"] is not None else ""
            if not block:
                continue
            rows.append({
                "district": "Erode",
                "block": block,
                "village": name,
                "census_code": cells[idx["code"]].strip() if idx["code"] is not None else None,
                "population": _num(cells[idx["population"]]) if idx["population"] is not None else None,
                "households": _num(cells[idx["households"]]) if idx["households"] is not None else None,
                "area_ha": _num(cells[idx["area"]]) if idx["area"] is not None else None,
                "gram_panchayat": cells[idx["panchayat"]].strip() if idx["panchayat"] is not None else None,
                "census_year": 2011,
            })
    return rows


def scrape(out_path: Path, fetch_text=None):
    fetcher = Fetcher() if fetch_text is None else None
    district = fetcher.get(DISTRICT_URL)
    urls = taluk_urls(district)
    if not urls:
        raise RuntimeError("no taluk URLs discovered on district page")
    log.info("discovered %d taluk pages", len(urls))

    all_rows = []
    for url in sorted(urls):
        page = fetcher.get(url)
        rows = extract_villages(page)
        all_rows.extend(rows)
        log.info("%-32s %d villages", url.rsplit("/", 2)[-2], len(rows))

    # de-duplicate by (block, village)
    seen = {}
    for r in all_rows:
        key = (r["block"], r["village"])
        if key not in seen:
            seen[key] = r
    rows = list(seen.values())
    rows.sort(key=lambda r: (r["block"], r["village"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return rows


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BASE_DIR / "data" / "scrape" / "erode_villages"
                                         / "erode_villages.jsonl"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = scrape(Path(args.out))
    blocks = sorted({r["block"] for r in rows})
    total_pop = sum(r["population"] or 0 for r in rows)
    log.info("scraped %d villages across %d blocks; total pop %s",
             len(rows), len(blocks), f"{total_pop:,}")
    log.info("blocks: %s", ", ".join(blocks))
    log.info("wrote -> %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
