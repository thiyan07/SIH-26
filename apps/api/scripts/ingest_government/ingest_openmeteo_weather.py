"""Ingest historical weather (rainfall, temperature) for Erode locations from
the Open-Meteo Historical Weather API.

Open-Meteo's archive API is free and keyless; it serves ERA5 reanalysis (the
same reanalysis family that underpins IMD-grade climatology studies, though it
is *not* the IMD gridded product).  With proper provenance this is far better
than nothing: the analysis' ``WeatherStatistic`` reader currently has zero rows.

Data model (per weather_statistics row):
  indicator = rainfall|temperature, period = "YYYY" (annual), unit = mm|degC
  value = annual precipitation sum / annual mean 2m temperature
  years 2020..2024 inclusive, aggregated from daily series client-side.

Usage:
  python -m scripts.ingest_government.ingest_openmeteo_weather
  python -m scripts.ingest_government.ingest_openmeteo_weather --years 2018 2019

License: Open-Meteo data is CC-BY-4.0; source attribution is recorded in the
row provenance (source_name="Open-Meteo (ERA5)").
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from app.db.models import DataSnapshot, Location, WeatherStatistic
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_openmeteo_weather")

API = "https://archive-api.open-meteo.com/v1/archive"
SOURCE_NAME = "Open-Meteo (ERA5)"
SOURCE_URL = "https://open-meteo.com/"
DATASET_NAME = "Open-Meteo Historical Weather Data (archive API)"
UA = "GramBizAI/1.0 (erode weather ingest; keyless public API)"

DEFAULT_YEARS = [2024, 2023, 2022, 2021, 2020]


def fetch_annual(lat: float, lon: float, years: list[int]) -> dict:
    start, end = f"{min(years)}-01-01", f"{max(years)}-12-31"
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": "precipitation_sum,temperature_2m_mean",
        "timezone": "Asia/Kolkata",
    })
    req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - open-meteo public API
        payload = __import__("json").load(resp)
    daily = payload.get("daily", {})
    times = daily.get("time", [])
    rainday = daily.get("precipitation_sum", [])
    tempday = daily.get("temperature_2m_mean", [])
    from collections import defaultdict
    rain = defaultdict(float)
    tcount, tsum = defaultdict(int), defaultdict(float)
    for i, ts in enumerate(times):
        year = int(ts[:4])
        if ts[:4] not in {str(y) for y in years}:
            continue
        if rainday and rainday[i] is not None:
            rain[year] += float(rainday[i] or 0.0)
        if tempday and tempday[i] is not None:
            tsum[year] += float(tempday[i])
            tcount[year] += 1
    return {
        "rainfall": {y: round(rain[y], 1) for y in years},
        "temperature": {y: round(tsum[y] / tcount[y], 1) if tcount[y] else None for y in years},
    }


def upsert_weather(session, location_id, indicator, unit, years, values, snapshot):
    for y in years:
        v = values.get(y)
        if v is None:
            continue
        row = session.query(WeatherStatistic).filter(
            WeatherStatistic.location_id == location_id,
            WeatherStatistic.indicator == indicator,
            WeatherStatistic.period == str(y),
        ).first()
        if row:
            row.value = v
        else:
            session.add(WeatherStatistic(
                location_id=location_id, level="village", indicator=indicator,
                period=str(y), value=v, unit=unit,
                source_name=SOURCE_NAME, source_url=SOURCE_URL,
                dataset_name=DATASET_NAME, source_type="weather",
                retrieved_at=datetime.now(timezone.utc),
                geographic_level="point",
                reference_year=y,
                confidence="medium",
                is_estimate=True,   # ERA5 reanalysis, not ground-station measurement
                is_demo=False,
                methodology="ERA5 reanalysis (Open-Meteo archive API) daily "
                            "precipitation_sum / temperature_2m_mean aggregated "
                            "to annual total / mean. Reanalysis, not IMD "
                            "gridded station data.",
            ))
            snapshot.records_ingested += 1
    session.flush()


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=DEFAULT_YEARS,
                    help="calendar years to aggregate (default 2020..2024)")
    ap.add_argument("--location", help="restrict to one Location village name")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    years = sorted({y for y in args.years})

    snapshot = DataSnapshot(job_name="weather_openmeteo_erode", status="running",
                            records_ingested=0,
                            started_at=datetime.now(timezone.utc))
    with session_scope() as s:
        register_data_source(s, "weather", "Weather (Open-Meteo ERA5)",
                             "weather", "weather_statistics",
                             "Historical rainfall/temperature (ERA5 reanalysis)")
        locs = s.query(Location).filter(
            Location.state == "Tamil Nadu", Location.district == "Erode"
        ).all()
        if args.location:
            locs = [loc for loc in locs if loc.village == args.location]
        log.info("fetching weather for %d Erode locations, years %s", len(locs), years)
        for i, loc in enumerate(locs):
            try:
                agg = fetch_annual(loc.latitude, loc.longitude, years)
            except Exception as exc:  # noqa: BLE001 - keep going on flaky network
                log.warning("  ERA5 fetch failed for %s: %s", loc.village, exc)
                time.sleep(0.4)
                continue
            upsert_weather(s, loc.id, "rainfall", "mm", years, agg["rainfall"], snapshot)
            upsert_weather(s, loc.id, "temperature", "degC", years, agg["temperature"], snapshot)
            if (i + 1) % 10 == 0:
                log.info("  %d/%d locations", i + 1, len(locs))
            time.sleep(0.4)  # be polite; keyless public API
        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    log_event("ingest", job="weather_openmeteo_erode",
              locations=len(locs), years=years,
              records=snapshot.records_ingested, status="completed")
    log.info("weather rows written: %d", snapshot.records_ingested)
    return 0


if __name__ == "__main__":
    sys.exit(main())
