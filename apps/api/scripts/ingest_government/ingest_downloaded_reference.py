"""Ingest user-downloaded official datasets into the indicator/market-name tables.

These files were downloaded by the maintainer from data.gov.in / Agmarknet and
placed under ``data/raw`` (see the module docstring of each parser). They are
national- or state-level series and therefore do NOT fit the Erode-pinned
schema (``agriculture_statistics``, ``weather_statistics``, etc.), so they are
stored in the generic fact tables:

* ``indicator_statistics``  - national/state indicator time-series
  * pesticide consumption (chemical / bio / total, MT, 2017-18..2021-22)
  * textiles & apparel exports (US$ values, 2017-18..2022-23)
  * retail-outlet class counts by State/UT (A-E class + total, snapshot)
* ``market_names``          - APMC contact-market name directory (Meghalaya,
  from the AGMARKNET ``Market Name`` workbook) for normalizing ``market_name``.

All values are taken verbatim from the source files and never fabricated;
``confidence`` is medium (official spreadsheets, not ground truth), provenance
is real and attributed, and real rows are unique so re-runs are idempotent.

Usage:
  python -m scripts.ingest_government.ingest_downloaded_reference
  python -m scripts.ingest_government.ingest_downloaded_reference --dry-run
  python -m scripts.ingest_government.ingest_downloaded_reference \
      --pesticide --skip-market-names
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import DataSnapshot, IndicatorStatistic, MarketName
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_downloaded_reference")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
GOV_RAW = BASE_DIR / "data" / "raw" / "gov_indicator"
MARKET_RAW = BASE_DIR / "data" / "raw" / "market_names"

# Source attribution
PEST_SOURCE = "Rajya Sabha Q&A (data.gov.in) - chemical & bio-pesticide consumption"
PEST_URL = "data/raw/gov_indicator/pesticide_consumption.csv"
EXPORT_SOURCE = "Rajya Sabha Q&A (data.gov.in) - textiles & apparel exports"
EXPORT_URL = "data/raw/gov_indicator/textiles_exports.csv"
OUTLET_SOURCE = "Rajya Sabha Q&A (data.gov.in) - retail outlet classes by State/UT"
OUTLET_URL = "data/raw/gov_indicator/retail_outlets_by_state.csv"
MARKET_SOURCE = "AGMARKNET Market Name directory (Meghalaya)"
MARKET_URL = "data/raw/market_names/meghalaya_market_names.xls"

_METRO = ("2017-18", "2018-19", "2019-20", "2020-21", "2021-22")


def _num(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("−", "-")
    if not text or text in ("-", "--", "na", "n/a", ""):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean_header(h: str) -> str:
    return (h or "").strip().lower().replace("\n", " ").replace("\r", " ")


# ---------------------------------------------------------------------------
# Pesticide consumption: national annual chemical / bio / total (MT)
# ---------------------------------------------------------------------------
def parse_pesticide(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            period = (raw.get("Year") or "").strip()
            if not period or period.lower() == "year":
                continue
            mappings = [
                ("chemical", "Consumption (in MT TG) - Chemical Pesticides", "MT"),
                ("bio", "Consumption (in MT TG) - Bio-Pesticides", "MT"),
                ("total", "Consumption (in MT TG) - Total", "MT"),
            ]
            for dimension, col, unit in mappings:
                val = _num(raw.get(col))
                if val is None:
                    continue
                rows.append({
                    "indicator": "pesticide_consumption",
                    "period": period,
                    "value": val,
                    "unit": unit,
                    "dimension": dimension,
                    "dimension_type": "type",
                    "state": None, "district": None,
                    "source": PEST_SOURCE, "url": PEST_URL,
                    "dataset": "National chemical & bio-pesticide consumption (MT)",
                    "method": "Verbatim figures from the downloaded Rajya Sabha Q&A "
                              "spreadsheet for chemical, bio and total pesticide "
                              "consumption in metric tonnes.",
                })
    return rows


# ---------------------------------------------------------------------------
# Textiles & apparel exports: national annual (US$ bn, per the source)
# This file is transposed: the header row holds the year labels and the single
# data row holds the label ("Textiles & apparel exports...") in the Year column
# with a value under each year column.
# ---------------------------------------------------------------------------
def parse_exports(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            label = (raw.get("Year") or "").strip()
            if not label or label.lower() == "year":
                continue
            for col, value in raw.items():
                col = (col or "").strip()
                if not col or col.lower() == "year" or not col:
                    continue
                val = _num(value)
                if val is None:
                    continue
                rows.append({
                    "indicator": "textiles_apparel_exports",
                    "period": col,
                    "value": val,
                    "unit": "USD billion",
                    "dimension": None,
                    "dimension_type": None,
                    "state": None, "district": None,
                    "source": EXPORT_SOURCE, "url": EXPORT_URL,
                    "dataset": "National textiles & apparel exports (incl. handicrafts)",
                    "method": "Verbatim figure from the downloaded Rajya Sabha Q&A "
                              "spreadsheet for textiles & apparel exports including "
                              "handicrafts (per the source, in billions of US dollars).",
                })
    return rows


# ---------------------------------------------------------------------------
# Retail outlet classes by State/UT (snapshot, no year stated by the source)
# ---------------------------------------------------------------------------
def parse_outlets(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            state = (raw.get("State /UT") or "").strip()
            if not state or state.lower() in ("state /ut", "state/ut") or state.isdigit():
                continue
            dims = [
                ("A class (Urban)", "A"),
                ("B class (Urban)", "B"),
                ("C class (Semi Urban)", "C"),
                ("D class (Highways NH and SH)", "D"),
                ("E class (Rural)", "E"),
                ("Total", "Total"),
            ]
            for col, dimension in dims:
                val = _num(raw.get(col))
                if val is None:
                    continue
                rows.append({
                    "indicator": "retail_outlet_classes",
                    "period": "snapshot",
                    "value": val,
                    "unit": "count",
                    "dimension": dimension,
                    "dimension_type": "outlet_class",
                    "state": state,
                    "district": None,
                    "source": OUTLET_SOURCE, "url": OUTLET_URL,
                    "dataset": "Retail outlet classes by State/UT (A-E + total)",
                    "method": "Verbatim outlet-class counts from the downloaded "
                              "Rajya Sabha Q&A spreadsheet, attributed per "
                              "State/UT. The source gives no single reference "
                              "year, so period is recorded as 'snapshot'.",
                })
    return rows


# ---------------------------------------------------------------------------
# AGMARKNET market-name directory (Meghalaya, .xls workbook)
# ---------------------------------------------------------------------------
def parse_market_names(path: Path) -> list[dict]:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover - only when extra not installed
        log.error("xlrd is required to read the .xls market directory "
                  "(install `pip install -e '.[data]'` or `pip install xlrd`)")
        raise SystemExit(2) from exc
    wb = xlrd.open_workbook(str(path))
    sh = wb.sheet_by_index(0)
    rows = []
    for r in range(sh.nrows):
        district, _block, name = sh.row_values(r)[:3]
        district = str(district or "").strip()
        name = str(name or "").strip()
        if not name or name.lower() == "market name" or not district:
            continue
        rows.append({
            "state": "Meghalaya",
            "district": district,
            "name": name,
        })
    return rows


def _store_indicators(session, snapshot, rows) -> int:
    added = 0
    for rec in rows:
        dupe = session.query(IndicatorStatistic).filter(
            IndicatorStatistic.indicator == rec["indicator"],
            IndicatorStatistic.period == rec["period"],
            IndicatorStatistic.state == rec["state"],
            IndicatorStatistic.dimension == rec["dimension"],
        ).first()
        if dupe:
            continue
        session.add(IndicatorStatistic(
            indicator=rec["indicator"],
            period=rec["period"],
            value=rec["value"],
            unit=rec["unit"],
            state=rec["state"],
            district=rec["district"],
            dimension=rec["dimension"],
            dimension_type=rec["dimension_type"],
            source_name=rec["source"],
            source_url=rec["url"],
            dataset_name=rec["dataset"],
            source_type="government",
            reference_year=_ref_year(rec["period"]),
            retrieved_at=datetime.now(timezone.utc),
            geographic_level="national" if not rec["state"] else "state",
            confidence="medium",
            completeness=1.0,
            methodology=rec["method"],
            is_estimate=False,
            is_demo=False,
        ))
        added += 1
    return added


def _ref_year(period) -> int | None:
    if not period or period == "snapshot":
        return None
    head = str(period).split()[0].split("-")[0]
    try:
        return int(head)
    except ValueError:
        return None


def _store_market_names(session, snapshot, rows) -> int:
    added = 0
    for rec in rows:
        dupe = session.query(MarketName).filter(
            MarketName.state == rec["state"],
            MarketName.district == rec["district"],
            MarketName.name == rec["name"],
        ).first()
        if dupe:
            continue
        session.add(MarketName(
            state=rec["state"],
            district=rec["district"],
            name=rec["name"],
            source_name=MARKET_SOURCE,
            source_url=MARKET_URL,
            dataset_name="AGMARKNET Market Name directory",
            source_type="government",
            reference_year=2013,
            retrieved_at=datetime.now(timezone.utc),
            geographic_level="district",
            confidence="medium",
            completeness=1.0,
            methodology="Verbatim market (mandi) names from the downloaded "
                        "AGMARKNET 'Market Name' workbook, grouped by district "
                        "for Meghalaya; used to normalize market_name values.",
            is_estimate=False,
            is_demo=False,
        ))
        added += 1
    return added


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Ingest downloaded official reference datasets")
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    ap.add_argument("--pesticide", action="store_true",
                    help="include pesticide consumption (default on)")
    ap.add_argument("--skip-pesticide", action="store_true")
    ap.add_argument("--exports", action="store_true",
                    help="include textiles exports (default on)")
    ap.add_argument("--skip-exports", action="store_true")
    ap.add_argument("--outlets", action="store_true",
                    help="include retail outlet classes (default on)")
    ap.add_argument("--skip-outlets", action="store_true")
    ap.add_argument("--market-names", action="store_true",
                    help="include Meghalaya market-name directory (default on)")
    ap.add_argument("--skip-market-names", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    jobs = []
    if not args.skip_pesticide:
        jobs.append(("pesticide_consumption", PEST_SOURCE, "indicator", "pesticide",
                     parse_pesticide(GOV_RAW / "pesticide_consumption.csv"), "pesticide_consumption"))
    if not args.skip_exports:
        jobs.append(("textiles_exports", EXPORT_SOURCE, "indicator", "exports",
                     parse_exports(GOV_RAW / "textiles_exports.csv"), "textiles_exports"))
    if not args.skip_outlets:
        jobs.append(("retail_outlets", OUTLET_SOURCE, "indicator", "outlets",
                     parse_outlets(GOV_RAW / "retail_outlets_by_state.csv"), "retail_outlet_classes"))
    if not args.skip_market_names:
        jobs.append(("market_names", MARKET_SOURCE, "market", "market_names", [], ""))

    snapshot = DataSnapshot(job_name="downloaded_reference_data", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        if jobs:
            register_data_source(
                s, "gov_indicator_reference",
                "National/state indicator series + market-name directory",
                "indicator", "indicator_statistics",
                "Official downloaded datasets stored in the generic "
                "indicator_statistics and market_names tables; refresh on "
                "updated downloads.")
        for name, source, kind, stub, rows, _label in jobs:
            if kind == "market":
                parsed = parse_market_names(MARKET_RAW / "meghalaya_market_names.xls")
                added = _store_market_names(s, snapshot, parsed)
                if args.dry_run:
                    print(f"[dry-run] {name}: {len(parsed)} market names")
                else:
                    log.info("%s: stored %d market names", name, added)
            else:
                if args.dry_run:
                    print(f"[dry-run] {name}: {len(rows)} indicator rows")
                else:
                    added = _store_indicators(s, snapshot, rows)
                    log.info("%s: stored %d indicator rows", name, added)
        snapshot.status = "dry_run" if args.dry_run else "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    if not args.dry_run:
        log_event("ingest", job="downloaded_reference_data",
                  records=snapshot.records_ingested, status="completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
