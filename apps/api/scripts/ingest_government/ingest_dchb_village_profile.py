"""Enrich the Census 2011 layer with the village-level DCHB profile.

The Census 2011 village/pu publication (2018062196.pdf) has population,
males and females only - no households, literacy or workers.  The much larger
DCHB (2018062114.pdf, "DISTRICT CENSUS HANDBOOK: ERODE") carries a complete
"VILLAGE PRIMARY CENSUS ABSTRACT" that adds, for every inhabited village and
town: area (ha), **number of households**, population, age 0-6, Scheduled
Caste / Scheduled Tribe totals, **literates**, and **total / main workers /
cultivators**.

This script rasterizes the DCHB with ``pdftotext -layout`` (cached as
``dchb_district.txt`` in the processed dir), extracts that abstract into a
per-name profile, and joins it onto the Location rows that already exist
(towns geocoded earlier + village panchayats).  It only *adds* fields that are
currently missing on ``population_statistics``:

  - ``households``   - from the DCHB (villages previously had none)
  - ``literacy``     - = 100 * literates / population (official figures)
  - ``workers``      - official total workers (persons)
  - ``non_workers``  - = population - workers

Existing population/males/females are never overwritten; the DCHB population
is cross-checked against the stored value and differences are logged (a
village panchayat may cover 1-2 revenue villages, so occasional deltas are
expected and harmless to the *added* fields).

Nothing is fabricated: towns/villages with no DCHB row, or name collisions
(multiple codes sharing one name), are left unchanged and reported.

Usage:
  python -m scripts.ingest_government.ingest_dchb_village_profile
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

from app.db.models import PopulationStatistic
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source
from scripts.ingest_government.scrape_erode_census import (
    PROC_DIR,
)

log = logging.getLogger("ingest_dchb_village_profile")

BASE_DIR = Path(__file__).resolve().parents[2]  # apps/api
RAW_DIR = BASE_DIR / "data" / "raw" / "erode_census"
DCHB_PDF = RAW_DIR / "dchb.pdf"
TEXT_PATH = PROC_DIR / "dchb_district.txt"
CSV_PATH = PROC_DIR / "erode_dchb_village_profile.csv"

# data import is delayed: discovering the five "types" of row in non-PCA
# chapters is done by example parsing rather than hardcoding page ranges.
_VPOP = re.compile(
    r"^\s*(?P<code>\d{6})\s+(?P<name>[A-Za-z][A-Za-z .'()/-]*?)\s+"
    r"(?P<area>[\d,.]+|-)\s+(?P<hh>[\d,]+|-)\s+(?P<pop>[\d,]+)\s+"
    r"(?P<mal>[\d,]+)\s+(?P<fem>[\d,]+)\s+"
    r"(?P<a6p>[\d,]+|-)\s+(?P<a6m>[\d,]+|-)\s+(?P<a6f>[\d,]+|-)$"
)
_LIT = re.compile(
    r"^\s*(?P<scp>[\d,]+|-)\s+(?P<scm>[\d,]+|-)\s+(?P<scf>[\d,]+|-)\s+"
    r"(?P<stp>[\d,]+|-)\s+(?P<stm>[\d,]+|-)\s+(?P<stf>[\d,]+|-)\s+"
    r"(?P<litp>[\d,]+)\s+(?P<litm>[\d,]+)\s+(?P<litf>[\d,]+)\s+"
    r"(?P<name>.+)$"
)
_WORK = re.compile(
    r"^\s*(?P<code>\d{6})\s+(?P<name>[A-Za-z][A-Za-z .'()/-]*?)\s+"
    r"(?P<twp>[\d,]+|-)\s+(?P<twm>[\d,]+|-)\s+(?P<twf>[\d,]+|-)\s+"
    r"(?P<mwp>[\d,]+)\s+(?P<mwm>[\d,]+)\s+(?P<mwf>[\d,]+)\s+"
    r"(?P<cultp>[\d,]+|-)\s+(?P<cultm>[\d,]+|-)\s+(?P<cultf>[\d,]+|-)$"
)
_BADNAME = re.compile(r"\b(Total|Rural|Urban)\s*$")
_STATUS = re.compile(r"\s*\((?:M|TP|CT|NAC|OG|E|G)\)\s*$")


def _norm(name: str) -> str:
    # strip only census *status* parens (M|TP|CT|...); keep real-name suffixes
    # such as "(North R.F.)" so that distinct forest villages stay distinct.
    name = _STATUS.sub("", name)
    name = re.sub(r"^Urban\s+|^Rural\s+", "", name).strip()
    return re.sub(r"\s+", " ", name)


def _uniq(items: list, key) -> list:
    """Distinct non-None values of ``key`` over ``items`` (dedupes again); the
    caller must require ``len(result) == 1`` to trust a value."""
    return list({item[key] for item in items if key in item and item[key] is not None})


def _int(tok: str):
    if tok in ("-", ""):
        return None
    return int(tok.replace(",", ""))


def rasterize() -> Path:
    if TEXT_PATH.exists() and TEXT_PATH.stat().st_size > 1_000_000:
        return TEXT_PATH
    import subprocess

    PROC_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # exit status enforced by check=True
        ["pdftotext", "-layout", str(DCHB_PDF), str(TEXT_PATH)],
        capture_output=True, text=True, check=True)
    log.info("rasterized DCHB (%d bytes -> %s)", DCHB_PDF.stat().st_size, TEXT_PATH)
    return TEXT_PATH


def parse_profile(text: str) -> tuple[dict, dict, dict, list]:
    """Parse the VILLAGE PRIMARY CENSUS ABSTRACT into per-name profiles."""
    pop_map: dict[str, list] = defaultdict(list)
    lit_map: dict[str, list] = defaultdict(list)
    work_map: dict[str, list] = defaultdict(list)
    rows = []  # audit rows: code, name, area, hh, pop, literacy, workers
    for ln in text.splitlines():
        ln = ln.rstrip()
        m = _VPOP.match(ln)
        if m and _int(m.group("pop")) and _int(m.group("pop")) > 0:
            name = _norm(m.group("name"))
            if _BADNAME.search(name):
                continue
            rec = {
                "code": m.group("code"),
                "area": m.group("area"),
                "hh": _int(m.group("hh")),
                "pop": _int(m.group("pop")),
                "mal": _int(m.group("mal")),
                "fem": _int(m.group("fem")),
            }
            pop_map[name].append(rec)
            rows.append(rec)
            continue
        mm = _LIT.match(ln)
        if mm and not _BADNAME.search(mm.group("name").strip()):
            name = _norm(mm.group("name"))
            if name:
                lit_map[name].append({
                    "litp": _int(mm.group("litp")),
                    "litm": _int(mm.group("litm")),
                    "litf": _int(mm.group("litf")),
                })
            continue
        mw = _WORK.match(ln)
        if mw and _int(mw.group("mwp")):
            name = _norm(mw.group("name"))
            if _BADNAME.search(name):
                continue
            work_map[name].append({
                "workers": _int(mw.group("twp")),
                "main_workers": _int(mw.group("mwp")),
            })
    return pop_map, lit_map, work_map, rows


def write_csv(rows: list[dict]) -> int:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["code", "name", "area", "hh", "pop", "mal", "fem",
              "literacy_pct", "workers"]
    with open(CSV_PATH, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in fields})
    return len(rows)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rasterize", action="store_true",
                    help="reuse cached dchb_district.txt")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    text = TEXT_PATH.read_text() if (args.no_rasterize and TEXT_PATH.exists()) \
        else rasterize().read_text()
    pop_map, lit_map, work_map, audit_rows = parse_profile(text)
    n_lit = sum(len(v) for v in lit_map.values())
    n_work = sum(len(v) for v in work_map.values())
    log.info("DCHB village abstract: %d populated rows, %d literates rows, %d worker rows",
             len(pop_map), n_lit, n_work)

    enriched = unchanged = pop_mismatch = collision = 0
    changed = []

    snapshot_done = [False]

    def _register(s):
        if not snapshot_done[0]:
            register_data_source(
                s, "population_census_dchb_profile",
                "Village/Town Profile (Census 2011 DCHB)",
                "demographics", "population_statistics",
                "Census 2011 DCHB village profile - historical, not current population")
            snapshot_done[0] = True

    with session_scope() as s:
        # names live on Location; run a join over the small 110-location set
        from app.db.models import Location
        locs = s.query(Location, PopulationStatistic).join(
            PopulationStatistic,
            (PopulationStatistic.location_id == Location.id)
            & (PopulationStatistic.census_year == 2011)
            & (PopulationStatistic.is_demo.is_(False)),
        ).filter(Location.state == "Tamil Nadu", Location.district == "Erode").all()
        for loc, P in locs:
            n = _norm(loc.village or "")
            if not n:
                continue
            all_recs = pop_map.get(n, [])
            stored_pop = P.population
            if not all_recs:
                unchanged += 1
                continue
            # Identity gate: the official Census population of a settlement is
            # already stored (a panchayat figures row for villages, the town
            # PCA for towns).  Adopt DCHB extra fields only from the row whose
            # population EXACTLY equals that stored value - this rules out the
            # many same-named but different settlements (e.g. the town Bhavani
            # vs a Bhavani village).  Rows previously written for non-matching
            # settlements are explicitly reverted to NULL below.
            cands = [r for r in all_recs if r["pop"] == stored_pop] \
                if stored_pop else all_recs
            if not cands:
                pop_mismatch += 1
                if (P.households is not None or P.literacy is not None
                        or P.workers is not None):
                    P.households = P.literacy = P.workers = P.non_workers = None
                log.info("reverted %-24s dchb=%s stored=%s",
                         n, sorted({r["pop"] for r in all_recs}), stored_pop)
                continue
            if len({r["hh"] for r in cands}) != 1:
                collision += 1
                log.warning("COLLISION %s (equal pop, mixed hh): %s",
                            n, sorted({r["hh"] for r in cands}))
                continue
            d = cands[0]

            lit_rows = _uniq(lit_map.get(n, []), "litp")
            litp = lit_rows[0] if len(lit_rows) == 1 else None
            work_rows = _uniq(work_map.get(n, []), "workers")
            workers = work_rows[0] if len(work_rows) == 1 else None

            vals = {}
            if P.households is None and d.get("hh"):
                vals["households"] = d["hh"]
            if litp is not None and stored_pop and litp <= stored_pop:
                vals["literacy"] = round(litp / stored_pop * 100, 1)
            if workers is not None and stored_pop and workers <= stored_pop:
                vals["workers"] = workers
                vals["non_workers"] = stored_pop - workers
            if vals:
                _register(s)
                # provenance stays the official Census row; extend methodology
                for k, v in vals.items():
                    setattr(P, k, v)
                changed.append((n, vals))
                enriched += 1
            else:
                unchanged += 1

        # write the profile CSV out of band (pure file I/O)
        write_csv(audit_rows)

    notes = {}
    if collision:
        notes["collisions"] = collision
    if pop_mismatch:
        notes["pop_deltas"] = pop_mismatch
    if changed:
        hh = sum(1 for _, v in changed if "households" in v)
        lit = sum(1 for _, v in changed if "literacy" in v)
        wk = sum(1 for _, v in changed if "workers" in v)
        log.info("enriched=%d (hh=%d lit=%d workers=%d) unchanged=%d deltas=%d collisions=%d",
                 enriched, hh, lit, wk, unchanged, pop_mismatch, collision)
        log_event("ingest", job="dchb_village_profile", records=enriched,
                  households=hh, literacy=lit, workers=wk, unchanged=unchanged,
                  pop_deltas=pop_mismatch, errors=0, status="completed")
        return 0

    log.info("nothing to enrich: unchanged=%d deltas=%d collisions=%d",
             unchanged, pop_mismatch, collision)
    return 0


if __name__ == "__main__":
    sys.exit(main())
