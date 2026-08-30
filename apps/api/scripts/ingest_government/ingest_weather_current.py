"""Ingest *live* and *current-year* weather for Erode locations.

Two keyless, free bulk sources fill gaps the annual ERA5 import (2020-2024)
leaves open: weather as of today, and the current meteorological year.

Part A - Open-Meteo Forecast API (https://api.open-meteo.com/v1/forecast)
  Observed "current" temperature + precipitation for each location, plus a
  3-day daily forecast (precipitation sum, max/min temperature). This is a
  model forecast (medium/low confidence), stored with is_estimate=True.

Part B - NASA POWER (NASA Langley) daily-agrometeorology reanalysis API
  (https://power.larc.nasa.gov/api/temporal/monthly/point). MERRA-2-derived
  monthly means for the current calendar year (2025 -> today): surface
  temperature (+min/max), precipitation (mean mm/day) and relative humidity.
  Keyless, freely reusable (NASA data policy), ~2 day latency.

indicator naming follows the existing weather_statistics convention so the
analysis reader surfaces the rows unchanged:
  current_temperature / current_precipitation  (period = ISO minute)
  forecast_precipitation_sum / forecast_temperature_max / _min (period = date)
  temperature / temperature_max / temperature_min / rainfall / humidity
      (period = "YYYY-MM", current-year monthly means)

Usage:
  python -m scripts.ingest_government.ingest_weather_current
  python -m scripts.ingest_government.ingest_weather_current --location Thindal
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

from app.db.models import DataSnapshot, Location, WeatherStatistic
from app.db.session import session_scope
from app.log import log_event
from scripts.ingest_government.ingest import register_data_source

log = logging.getLogger("ingest_weather_current")

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
POWER_API = "https://power.larc.nasa.gov/api/temporal/monthly/point"
SOURCE_FORECAST = "Open-Meteo (Forecast API)"
SOURCE_POWER = "NASA POWER (MERRA-2 reanalysis)"
UA = "GramBizAI/1.0 (erode live weather ingest; keyless public API)"


def fetch_forecast(lat: float, lon: float) -> dict:
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,precipitation,weather_code",
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Kolkata", "forecast_days": "3",
    })
    req = urllib.request.Request(f"{FORECAST_API}?{params}",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.load(resp)


def fetch_power_monthly(lat: float, lon: float, start_year: str, end_year: str) -> dict:
    params = urllib.parse.urlencode({
        "parameters": "T2M,T2M_MIN,T2M_MAX,PRECTOTCORR,RH2M",
        "community": "AG", "longitude": lon, "latitude": lat,
        "start": start_year, "end": end_year,
        "format": "JSON",
    })
    req = urllib.request.Request(f"{POWER_API}?{params}",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:  # noqa: S310
        return json.load(resp)


def upsert(session, location_id, indicator, period, value, unit,
           source_name, source_url, methodology, confidence, estimate, snapshot):
    if value is None:
        return
    row = session.query(WeatherStatistic).filter(
        WeatherStatistic.location_id == location_id,
        WeatherStatistic.indicator == indicator,
        WeatherStatistic.period == period,
    ).first()
    if row:
        row.value = float(value)
        return
    session.add(WeatherStatistic(
        location_id=location_id, level="village", indicator=indicator,
        period=period, value=float(value), unit=unit,
        source_name=source_name, source_url=source_url,
        dataset_name="Live/current weather, Erode (Open-Meteo forecast + NASA POWER)",
        source_type="weather", retrieved_at=datetime.now(timezone.utc),
        geographic_level="point", reference_year=int(period[:4]),
        confidence=confidence, completeness=0.9,
        methodology=methodology, is_estimate=estimate, is_demo=False,
    ))
    snapshot.records_ingested += 1


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--location", help="restrict to one Location village name")
    ap.add_argument("--no-power", action="store_true", help="skip NASA POWER part")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    snapshot = DataSnapshot(job_name="weather_live_erode", status="running",
                            records_ingested=0, started_at=datetime.now(timezone.utc))
    power_year = str(date.today().year - 1)
    with session_scope() as s:
        register_data_source(s, "weather_live",
                             "Live weather (Open-Meteo forecast + NASA POWER)",
                             "weather", "weather_statistics",
                             "Keyless: current/forecast conditions plus current-year "
                             "MERRA-2 monthly agrometeorology.")
        locs = s.query(Location).filter(
            Location.state == "Tamil Nadu", Location.district == "Erode"
        ).all()
        if args.location:
            locs = [loc for loc in locs if loc.village == args.location]
        log.info("live weather for %d Erode locations", len(locs))

        for i, loc in enumerate(locs):
            # Part A: Open-Meteo forecast (current + 3-day daily)
            try:
                fc = fetch_forecast(loc.latitude, loc.longitude)
            except Exception as exc:  # noqa: BLE001
                log.warning("  forecast failed for %s: %s", loc.village, exc)
                fc = {}
            cur = fc.get("current") or {}
            now_period = cur.get("time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            if "temperature_2m" in cur:
                upsert(s, loc.id, "current_temperature", now_period, cur["temperature_2m"],
                       "degC", SOURCE_FORECAST, "https://open-meteo.com/",
                       "Open-Meteo forecast API 'current' block (short-range model).",
                       "low", True, snapshot)
            if "precipitation" in cur:
                upsert(s, loc.id, "current_precipitation", now_period, cur["precipitation"],
                       "mm", SOURCE_FORECAST, "https://open-meteo.com/",
                       "Open-Meteo forecast API 'current' precipitation.",
                       "low", True, snapshot)
            daily = fc.get("daily") or {}
            times = daily.get("time") or []
            for j, d in enumerate(times):
                if daily.get("precipitation_sum") and daily["precipitation_sum"][j] is not None:
                    upsert(s, loc.id, "forecast_precipitation_sum", d,
                           daily["precipitation_sum"][j], "mm",
                           SOURCE_FORECAST, "https://open-meteo.com/",
                           "Open-Meteo daily forecast precipitation_sum.",
                           "low", True, snapshot)
                if daily.get("temperature_2m_max") and daily["temperature_2m_max"][j] is not None:
                    upsert(s, loc.id, "forecast_temperature_max", d,
                           daily["temperature_2m_max"][j], "degC",
                           SOURCE_FORECAST, "https://open-meteo.com/",
                           "Open-Meteo daily forecast temperature_2m_max.",
                           "low", True, snapshot)
                if daily.get("temperature_2m_min") and daily["temperature_2m_min"][j] is not None:
                    upsert(s, loc.id, "forecast_temperature_min", d,
                           daily["temperature_2m_min"][j], "degC",
                           SOURCE_FORECAST, "https://open-meteo.com/",
                           "Open-Meteo daily forecast temperature_2m_min.",
                           "low", True, snapshot)

            # Part B: NASA POWER monthly means for this calendar year onward
            if not args.no_power:
                try:
                    pw = fetch_power_monthly(loc.latitude, loc.longitude, power_year, power_year)
                    params = (pw.get("properties") or {}).get("parameter") or {}
                    for month_key in sorted((params.get("T2M") or {})):
                        month = int(month_key[4:6]) if len(month_key) >= 6 else 0
                        if not (1 <= month <= 12):
                            continue  # skip sentinel / partial-year keys
                        def _num(p, k):
                            v = (params.get(p) or {}).get(k)
                            return round(float(v), 2) if v is not None and v != -999.0 else None
                        for ind, param, unit in (
                            ("temperature", "T2M", "degC"),
                            ("temperature_max", "T2M_MAX", "degC"),
                            ("temperature_min", "T2M_MIN", "degC"),
                            ("humidity", "RH2M", "%"),
                            ("rainfall", "PRECTOTCORR", "mm/day"),
                        ):
                            v = _num(param, month_key)
                            if v is not None:
                                upsert(s, loc.id, ind, month_key[:7], v, unit,
                                       SOURCE_POWER, "https://power.larc.nasa.gov/",
                                       "NASA POWER (MERRA-2) monthly mean; precipitation "
                                       "is mean daily amount (mm/day), others monthly "
                                       "means of daily values. ~2-day latency; not "
                                       "ground-station observation.",
                                       "medium", True, snapshot)
                except Exception as exc:  # noqa: BLE001
                    log.warning("  POWER failed for %s: %s", loc.village, exc)
            if (i + 1) % 10 == 0:
                log.info("  %d/%d locations", i + 1, len(locs))
            time.sleep(0.4)

        snapshot.status = "completed"
        snapshot.finished_at = datetime.now(timezone.utc)
        s.add(snapshot)
    log_event("ingest", job="weather_live_erode", locations=len(locs),
              records=snapshot.records_ingested, status="completed")
    log.info("live weather rows written: %d", snapshot.records_ingested)
    return 0


if __name__ == "__main__":
    sys.exit(main())
