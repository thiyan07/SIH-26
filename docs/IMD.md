# IMD weather — status and integration plan (Phase 6)

## Status: NOT AVAILABLE KEYLESS — documented, not fabricated

The India Meteorological Department (IMD) is the authoritative national source
for gridded/daily rainfall and temperature. GramBiz cannot currently ingest it
through a public **keyless** endpoint:

- IMD’s own APIs are restricted to institutional access agreements.
- IMD products that appear on the Government of India Open Data portal
  (`api.data.gov.in`) require a free `DATA_GOV_API_KEY`, and the specific
  rainfall resource id must be confirmed against that key before use.

### What GramBiz does instead (never mislabelled as IMD)

| Source | Data | Status |
|---|---|---|
| **Open-Meteo ERA5** (CC-BY-4.0) | 2020–2024 annual rainfall/temperature per location | stored, provenance-tagged |
| **Open-Meteo forecast / current** | live temperature + precipitation + 3-day forecast (`is_estimate=True`) | stored |
| **NASA POWER** (MERRA-2) | current-year monthly temp/rain relative humidity | stored |
| **IMD** | would replace/override the above for rainfall | **unavailable without key + resource id** |

ERA5 is the same reanalysis family underpinning IMD-grade climatology studies;
it is *not* the IMD gridded product, and all rows say so in `source_name`.

## Integration plan (already wired, needs one confirmed id)

1. `scripts/ingest_government/ingest_imd_rainfall.py` — connection + provenance
   + storage runner. Fails fast (exit 2) without `DATA_GOV_API_KEY` **and**
   `IMD_RAINFALL_RESOURCE`; it never approximates rainfall and labels rows
   ``IMD``.
2. Normalisation is shared and fixture-tested:
   `scripts/ingest_government/normalize.py` → `DATAGOV_DEFS["imd_rainfall"]`
   (field-tolerant: `month`/`year`/`period`, `rainfall`/`rainfall_mm`/`value`,
   `unit`/`units`). Covered by `tests/test_ingest_government_normalize.py`.
3. DataSource ledger row `imd_rainfall` is registered (category `weather`,
   table `weather_statistics`, government/official provenance) with a
   freshness note explaining the key/resource requirement.
4. `/data-sources/providers` exposes the IMD provider with
   `state: config_missing` until the key plus resource id are configured.

## How to enable (operator action)

```bash
# in apps/api/.env  (never commit real values)
DATA_GOV_API_KEY=<free key from https://data.gov.in>
IMD_RAINFALL_RESOURCE=<resource id confirmed against your key>

python -m scripts.ingest_government.ingest_imd_rainfall
python -m scripts.ingest_government.ingest_imd_rainfall --state "Tamil Nadu" --district "Erode"
```