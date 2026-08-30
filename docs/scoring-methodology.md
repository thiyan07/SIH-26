# GramBiz AI — Scoring Methodology

## 1. Prototype Opportunity Index

The output is explicitly labelled a **"Prototype Opportunity Index"**, not a
scientifically validated universal formula. All weights are **configurable**
in the database (`opportunity_weights`).

### Component weights (default)

| Component | Weight | What it measures |
|-----------|--------|------------------|
| Demand Potential | 25% | Population, households, relevant establishments, market proximity, demand proxies |
| Competition Advantage | 20% | Mapped competitor count, density, distance, completeness |
| Accessibility | 15% | Distance to town/market/road, transport points |
| Price/Margin Potential | 15% | Sourced market/price data, category margin assumptions |
| Financial Fit | 15% | Capital adequacy vs. required project cost, working capital coverage |
| Risk | 10% | Inverse of exposure (competition, seasonality, supply chain, weather) |

### Normalization

Each component is normalized to 0–100. Missing inputs do not count toward the
denominator; instead they lower the **confidence score** and are surfaced in
the UI as "insufficient evidence".

```
overall_score =
  demand×0.25 + competition×0.20 + accessibility×0.15
  + price×0.15 + financial_fit×0.15 + (100 - risk)×0.10
```

Each sub-score is also returned (`demand_score, competition_score,
accessibility_score, price_score, financial_fit_score, risk_score`).

## 2. Demand Potential (0–100)

Built from whatever evidence is available:
- Population (Census 2011 baseline) and households
- Relevant nearby establishments (e.g. dairy demand proxies)
- Market infrastructure / distance to nearest market
- Category-specific demand proxies and available price/market data
- Optional search-interest provider

If population is unavailable/old, demand is computed on remaining evidence and
confidence is reduced.

## 3. Competition Advantage (0–100)

- `mapped_competitors_5km`, `mapped_competitors_10km`
- `competitors_per_1000_households`
- Competitor distance & clustering; overall business density
- **Data completeness indicator** (low/medium/high) acknowledging OSM does not
  capture every real business. Never claims an exact market participant count.

## 4. Accessibility (0–100)

- Distance to nearest town/city
- Distance to nearest market
- Distance to major road
- Nearby transport points (bus/rail) where available

## 5. Price / Margin Potential (0–100)

Uses **sourced** market/price data only. Reads ingested `market_prices`
rows (data.gov.in/Agmarknet mandi snapshots, stored with provenance; see
`app/engines/prices.py`). For the district, it picks the latest
`reference_date` per commodity, filters to category-relevant items, and
computes:

- `coverage` = matched relevant commodities / relevant commodity list
  (1.0 for categories without a curated list; any available item counts)
- `price_score` = `min(100, 40 + coverage × 50)` (rounded to 0.1)

If there are **no** ingested rows for the district the provider reports
`available: False`, the score stays neutral (`None` → normalised 50) and is
flagged low-confidence rather than fabricated — prices are never invented.

## 6. Financial Fit (0–100)

- Available capital vs. required project cost
- Working capital coverage relative to operating expenses
- Whether capital suffices without pushing margins

## 7. Risk (0–100, higher = more risk)

Inputs where data supports them:
- Competition intensity
- Seasonality
- Supply-chain / raw-material dependency
- Distance to market
- Weather sensitivity
- Buyer concentration

Risk is reported as a score (as in the dashboard "Risk: 55/100") and
integrated into the overall index as `(100 - risk)`.

## 8. Confidence Score

Every analysis computes a confidence level (`low` / `medium` / `high`) from:
- data availability
- data freshness (e.g. Census 2011 vs. current)
- geographic precision (point vs. village centroid)
- source reliability (government > OSM proxy > demo)
- completeness

The confidence is mandatory and always displayed, with a per-factor "Why"
breakdown:
```
Opportunity Score: 76/100
Confidence: Medium
Why:
- Population: Census 2011 baseline
- Business coverage: OSM, medium completeness
- Price data: recent
- Weather data: recent
```

## 9. Recommendation Rules (GO / MODIFY / AVOID)

- **GO** — overall score above a configurable threshold AND financial fit and
  risk acceptable.
- **MODIFY** — potentially viable but capital/scale/business-model should
  change (e.g. financial fit low but demand/competition fine).
- **AVOID** — significant risk or poor financial fit given evidence.

Language is always cautious: "appears potentially viable based on available
indicators." The system never guarantees success/failure.

## 10. Disclaimer

> Business opportunity scores are analytical estimates based on available
> data and are not guarantees of business success.
