# GramBiz AI — Data Licenses & Attribution

Every source is used only under a license that permits our use. **No Google
Maps / Google Places data is scraped or used** — only free, legitimate APIs and
official open data.

## Licence quick reference

| Source | Licence | Attribution required |
|--------|---------|---------------------|
| OpenStreetMap / Overpass (businesses, POIs, infrastructure, roads) | ODbL-1.0 | **Yes — "© OpenStreetMap contributors"** |
| Market / mandi prices (data.gov.in, MOA&FW) | GODL-India | Recommended attribution |
| UDYAM MSME unit list (data.gov.in OGD) | GODL-India | Recommended attribution (Ministry of MSME) |
| Registered Factories / ASI (MoSPI / Labour) | GODL-India / NDSAP | Recommended attribution |
| IMD rainfall | GODL-India | Recommended attribution (IMD) |
| Census of India 2011 | GODL-India | Recommended attribution |
| Soil Health Card (data.gov.in) | GODL-India | Recommended attribution (MOAFW) |
| Health facilities (GODL-India / Bharat Atlas) | GODL-India | Recommended attribution |

## ODbL / OpenStreetMap
- OSM is used under the **Open Database Licence (ODbL) 1.0**. Its map data is
  © OpenStreetMap contributors.
- Obligations in short: attribution on use, share-alike for extracted
  databases, and keeping the dataset open. GramBiz displays `"Mapped X"` and a
  data-completeness indicator rather than claiming exhaustive counts, and
  includes OSM attribution where OSM-derived evidence is shown.
- The ODbL licence is passed through in the quality registry (`license_id`).

## GODL-India
- Most Government of India datasets are published under the **Government Open
  Data Licence – India (GODL)**.
- It is effectively a public-domain-style licence; attribution to the publishing
  ministry is recommended and is recorded per source.

## Provenance fields (applied to every stored record)
Each `DataRecord` / source row carries:
`source_name`, `source_url`, `dataset_name`, `source_type` (`government`/`osm`/
`vendor`/`proxy`/`derived`), `reference_date`/`reference_year`,
`retrieved_at`, `geographic_level`, `confidence` (`low`/`medium`/`high`),
`methodology`, `is_estimate`, `is_demo`, plus `geographic_level` and confidence
metadata on the source-level catalog.

The **download/attribution obligations** that apply to rendered results are
tracked via each source's `license_id` in `SOURCE_QUALITY_CATALOG`
(`app/data_quality.py`) and surfaced in the data-source ledger produced by
`scripts/audit_data_sources.py`.

## API keys — never committed
Government APIs such as data.gov.in require a key. Keys are read from
environment variables (`DATA_GOV_API_KEY`, `UDYAM_RESOURCE`,
`UDYAM_PINCODE_DIRECTORY`), documented in `.env.example`, and **never** checked
into the repository. See the security notes in `README.md`.
