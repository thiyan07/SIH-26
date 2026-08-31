# GramBiz AI — Data Source Recommendation Matrix

Recommendations follow the task's priority tiers. `MUST HAVE` / `SHOULD HAVE`
are implemented; `OPTIONAL` / `ML TRAINING ONLY` / `REJECTED` are documented so
future work does not re-litigate the same decisions.

Legend for confidence: **V**=VERIFIED, **PV**=PARTIALLY_VERIFIED,
**NV**=UNVERIFIED. `L/Q` = license / overall quality overview (see
`DATA_QUALITY.md` for exact 0-100 scores).

## MUST HAVE
| Source | Tier | Level | Status | Confidence | Notes |
|--------|------|-------|--------|-----------|-------|
| OpenStreetMap (OSM/Overpass) | 1 | point | **Implemented** | V | Primary competitor & infrastructure source. |
| UDYAM MSME registrations (data.gov.in OGD) | 1 | pincode | **Implemented** | V | `nearby_msmes` / `relevant_msmes`; key-gated. |
| AGMARKNET / official mandi prices (data.gov.in) | 1 | mandi | Implemented (prior) | V | Commodity prices & arrivals. |
| IMD rainfall | 1 | district | Implemented (prior) | V | Weather risk. |

## SHOULD HAVE
| Source | Tier | Level | Status | Confidence | Notes |
|--------|------|-------|--------|-----------|-------|
| Registered Factories / ASI | 1 | district | **Implemented (aggregate)** | PV | District-scoped only; not point-radius. |
| Census of India 2011 | 1 | village | Implemented (prior) | PV | Historical baseline; never called current. |
| Soil Health Card | 1 | district | Implemented (prior) | V | Soil-risk adjustment. |

## OPTIONAL
| Source | Tier | Level | Notes |
|--------|------|-------|-------|
| Bharat Atlas / place geometry | 1 | village/block | Base-layer lookup (already used). |
| RBI / NABARD / economic district stats | 2 | district | Value-add for capital/finance scoring. |
| GeM / public procurement | 2 | point/pincode | Optional demand signal. |

## ML TRAINING ONLY
| Source | Tier | Notes |
|--------|------|-------|
| Kaggle / GitHub / academic MSME & demand sets | 3 | Never exposed as authoritative; offline training only. |

## REJECTED / restricted
| Source | Tier | Reason |
|--------|------|--------|
| Google Maps / Google Places | — | ToS prohibits scraping; no licensed bulk access. |
| `udyogaadhaar.gov.in` scraping | — | Unstable, non-licensed, ToS-risky. |
| Reddit / community boards | 4 | `COMMUNITY_SIGNAL` only — supporting, never authoritative. |

## Tier definitions
- **Tier 1** — official Indian government APIs + OSM + official market/weather.
- **Tier 2** — maintained open-source / derived datasets.
- **Tier 3** — Kaggle / GitHub / academic (Kaggle = `ML_TRAINING_ONLY` unless it
  adds verified geo coverage).
- **Tier 4** — Reddit (supporting only, never authoritative).

## Geographic-resolution policy
- **point** → full point-radius competitor & feature math (OSM).
- **pincode** → `nearby_msmes` / `relevant_msmes` scoped to the pincode; reduced
  confidence; never presented as exact-point competitors (UDYAM).
- **district** → `industrial_units` and other aggregates only (factories, census
  rollups); cannot answer point-radius questions directly.
