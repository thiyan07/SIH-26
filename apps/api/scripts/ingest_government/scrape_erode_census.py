"""Collect official Census 2011 population data for Erode district, Tamil Nadu.

Source is the Government of Tamil Nadu Erode district portal (erode.nic.in),
which publishes Census of India 2011 extracts as free public PDFs (Government
Open Data; keyless download, no captcha).  We download them once, rasterize
tables with `pdftotext -layout`, and normalize into the same row schema the
`census` ingestion path expects:

    {state, district, block, village, population, households,
     males, females, census_year}

`--promote` replaces any existing DEMO population rows for the matched
village/CT towns with the official Census figures (is_demo=False).

Usage:
  python -m scripts.ingest_government.scrape_erode_census        # fetch + build CSV
  python -m scripts.ingest_government.scrape_erode_census --promote  # replace demo rows in DB

PDF list (Census of India 2011, Erode district - erode.nic.in/documents/census):
  - 2018062114.pdf  District Census Handbook Erode (village PCA incl. CT towns)
  - 2018062181.pdf  Town Panchayats Population 2011 (TP grade)
  - 2018062196.pdf  Village & Village Panchayat population by Panchayat Union
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.db.models import DataSnapshot, Location, PopulationStatistic
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("scrape_erode_census")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
RAW_DIR = BASE_DIR / "data" / "raw" / "erode_census"
PROC_DIR = BASE_DIR / "data" / "processed" / "erode_census"

# Official Erode district portal files (erode.nic.in -> documents/census).
PDFS = {
    "dchb": "https://cdn.s3waas.gov.in/s3bca82e41ee7b0833588399b1fcd177c7/uploads/2018/06/2018062114.pdf",
    "town_panchayats": "https://cdn.s3waas.gov.in/s3bca82e41ee7b0833588399b1fcd177c7/uploads/2018/06/2018062181.pdf",
    "villages": "https://cdn.s3waas.gov.in/s3bca82e41ee7b0833588399b1fcd177c7/uploads/2018/06/2018062196.pdf",
}
SOURCE_DOC = "https://erode.nic.in/documents/census/"

# Town names to promote, keyed by the name used in the DCHB PCA.
PROMOTE = [
    "Perundurai",      # Perundurai (TP)
    "Thindal",         # Thindal (CT)
    "Sathyamangalam",  # Sathyamangalam (M)
    "Bhavani",         # Bhavani (M)
]


def fetch_pdfs() -> dict[str, Path]:
    import urllib.request

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, url in PDFS.items():
        path = RAW_DIR / f"{key}.pdf"
        if path.exists() and path.stat().st_size > 1000:
            out[key] = path
            continue
        log.info("downloading %s -> %s", url, path.name)
        urllib.request.urlretrieve(url, path)  # noqa: S310 - official govt portal
        out[key] = path
    return out


def pdf_text(path: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout


def _num(text: str):
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


_TOWN_LINE = re.compile(
    r"(?P<code>\d{6})\s+(?P<name>[A-Za-z .'()-]+?)\s+"
    r"(?P<status>Urban|Rural|Total)?\s*"
    r"(?P<area>\d+\.\d+)\s+(?P<hh>[\d,]+)\s+(?P<pop>[\d,]+)\s+"
    r"(?P<males>[\d,]+)\s+(?P<females>[\d,]+)"
)


def parse_dchb_towns(text: str) -> list[dict]:
    """Parse 'Village Primary Census Abstract' town/CT rows from the DCHB.

    Row layout (pdftotext -layout, total-population section):
      code   Name (M|CT|TP)  Urban  area_ha  households  persons males females

    Only rows for inhabited towns/CTs with a decimal area field are captured
    (the SC/ST/literacy sub-tables have no area column and are ignored).
    The DCHB repeats the PCA three times, so rows are de-duplicated by town
    name keeping the first (total-population) occurrence.
    """
    rows = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = _TOWN_LINE.match(line.rstrip())
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group("name")).strip()
        if not re.search(r"\((M|CT|TP|NAC|OG)\)$", name):
            continue  # only town/Census-Town/TP rows carry households
        base = name.split(" (")[0].strip()
        if base in seen:
            continue  # first occurrence is the total-population row
        hh, pop, males, females = (_num(m.group(k)) for k in ("hh", "pop", "males", "females"))
        if pop is None or pop <= 0 or (males or 0) + (females or 0) != pop:
            continue  # sanity: males+females must equal total population
        seen.add(base)
        rows.append({
            "district": "Erode",
            "name": name,
            "households": hh,
            "population": pop,
            "males": males,
            "females": females,
        })
    return rows


def census_rows(towns: list[dict]) -> list[dict]:
    """Normalize to the ingest_census row schema for DB matching."""
    out = []
    for t in towns:
        base = t["name"].split(" (")[0].strip()
        out.append({
            "state": "Tamil Nadu",
            "district": "Erode",
            "block": base,
            "village": base,
            "population": t["population"],
            "households": t["households"],
            "males": t["males"],
            "females": t["females"],
            "census_year": 2011,
        })
    out.sort(key=lambda r: (r["village"], r["population"] or 0))
    return out


def write_csv(rows: list[dict], path: Path) -> int:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["state", "district", "block", "village", "population",
              "households", "males", "females", "census_year"]
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in fields})
    return len(rows)


def _coerce(val):
    if val is None or val == "":
        return None
    try:
        return int(float(str(val).replace(",", "")))
    except ValueError:
        return val


def adopt_census_rows(rows: list[dict]) -> int:
    """Replace demo PopulationStatistic rows with official Census figures.

    Matches Location by (state, district, block, village) where block==village
    (the seeded demo towns).  If a 2011 PopulationStatistic already exists for
    the Location it is overwritten; otherwise a new row is created.  Everything
    written here is flagged is_demo=False with Census provenance.
    """
    snapshot = DataSnapshot(job_name="census_erode_official", status="running",
                            started_at=datetime.now(timezone.utc))
    matched = 0
    with session_scope() as s:
        register_data_source(s, "population_census", "Population (Census 2011)",
                             "demographics", "population_statistics",
                             "Census 2011 baseline - historical, not current population")
        for r in rows:
            name = r["village"]
            pop, hh, males, females, cy = (
                _coerce(r.get("population")), _coerce(r.get("households")),
                _coerce(r.get("males")), _coerce(r.get("females")),
                _coerce(r.get("census_year", 2011)),
            )
            loc = s.query(Location).filter(
                Location.state == "Tamil Nadu",
                Location.district == "Erode",
                Location.block == name,
                Location.village == name,
            ).first()
            if loc is None:
                continue
            existing = s.query(PopulationStatistic).filter(
                PopulationStatistic.location_id == loc.id,
                PopulationStatistic.census_year == cy,
            ).first()
            values = {
                "population": pop,
                "households": hh,
                "males": males,
                "females": females,
                "census_year": cy,
                "reference_year": cy,
                "level": "village",
                "source_name": "Census India",
                "source_url": SOURCE_DOC,
                "dataset_name": "Primary Census Abstract (DCHB Erode, via erode.nic.in)",
                "source_type": "government",
                "confidence": "high",
                "is_estimate": False,
                "is_demo": False,
                "methodology": "Official Census of India 2011 figures from the Erode district "
                               "government portal (erode.nic.in/documents/census).",
            }
            if females and males:
                values["sex_ratio"] = round(females / males * 1000, 1)
            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
            else:
                s.add(PopulationStatistic(location_id=loc.id, **values))
            matched += 1
        snapshot.records_ingested = matched
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    log_event("ingest", job="census_erode_official", records=matched, errors=0, status="completed")
    return matched


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", action="store_true",
                    help="adopt official census figures into the DB (replaces demo rows)")
    ap.add_argument("--no-download", action="store_true",
                    help="parse already-downloaded PDFs only")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.promote:
        rows = read_csv(PROC_DIR / "erode_census_2011_towns.csv")
        if not rows:
            log.error("no processed CSV found; run collection first")
            return 1
        n = adopt_census_rows(rows)
        log.info("promoted official census rows for %d matched locations", n)
        return 0

    paths = {k: RAW_DIR / f"{k}.pdf" for k in PDFS}
    if not args.no_download:
        paths = fetch_pdfs()
    else:
        assert all(p.exists() for p in paths.values()), "run without --no-download once"

    dchb_text = pdf_text(paths["dchb"])
    towns = parse_dchb_towns(dchb_text)
    log.info("parsed %d town/CT rows from DCHB PCA", len(towns))

    rows = census_rows(towns)
    wanted = [t for t in rows if t["village"] in PROMOTE]
    log.info("PROMOTE set (%d):", len(wanted))
    for w in wanted:
        log.info("  %-16s pop=%-7s hh=%-6s m=%s f=%s",
                 w["village"], w["population"], w["households"], w["males"], w["females"])

    n = write_csv(rows, PROC_DIR / "erode_census_2011_towns.csv")
    write_csv(wanted, PROC_DIR / "erode_census_2011_promote.csv")
    log.info("wrote %d rows -> data/processed/erode_census/erode_census_2011_towns.csv", n)
    return 0


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    sys.exit(main())
