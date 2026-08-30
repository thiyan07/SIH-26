# GramBiz AI — Assumptions

This document records the explicit assumptions made during development so that
nothing is silently treated as fact.

## 1. Financial / Scheme Parameters

The following parameters come **from the supplied problem statement** (Problem
Statement ID 26091) and are treated as **assumed demo configuration**, not
verified government policy:

- Available margin = **10%** of project cost:
  `project_cost = available_margin / 0.10`
  `loan_amount = project_cost × 0.90`

### Micro Finance
- `project_cost <= ₹1.40 lakh`
- `loan max <= ₹1.25 lakh`
- interest `6.5%`, tenure `3 years`, moratorium `3 months`

### Term Loan
- `project_cost > ₹1.40 lakh` and `<= ₹50 lakh`
- `loan max <= ₹45 lakh`
- interest `8%`, tenure `7 years`, moratorium `6 months`

**All scheme parameters are stored in the `government_schemes` table and are
configurable.** They are clearly labelled as "based on the supplied problem
statement — verify with the relevant agency" until an official document is
retrieved, embedded, and verified.

## 2. Moratorium Treatment

Moratorium handling varies by actual loan rules. GramBiz builds a configurable
repayment engine supporting `interest_only_during_moratorium`,
`deferred_interest`, `principal_deferred`, and `custom_schedule`. The default
assumption for demo is `interest_only_during_moratorium` for both schemes, but
**the system does not claim a specific treatment is official** unless a
verified scheme document confirms it.

## 3. Population Baselines

- Census 2011 data is stored with `census_year = 2011`.
- It is always labelled **"Census 2011 baseline"** and never presented as
  current (2026) population.
- If a genuinely current official source becomes available, the population
  provider can replace/supplement the baseline.

## 4. OSM Business Coverage

- OSM does not list every real business in a village.
- All business counts are prefixed "Mapped" and carry a data-completeness
  indicator (low/medium/high).
- No exact "there are N competitors" claims are made.

## 5. Prices & Demand

- Local selling prices and demand are only reported from real data sources.
- Where unavailable, they are marked unavailable/estimated/proxy with
  methodology and limitations. Never fabricated as official.

## 6. Opportunity Index

- The "Prototype Opportunity Index" is a heuristic model, not a validated
  universal formula. Weights are configurable.

## 7. Demo Data

- Erode District demo data uses real administrative structure plus
  `is_demo=True` proxy values where real data was unavailable during
  development.
- Demo data is isolated and is never mixed with production-source data without
  the `is_demo` flag.

## 8. Sandbox / Deployment Assumption

- Docker is not available in this dev sandbox, so a local PostgreSQL 18
  cluster (initdb in the project tree) is used for verification.
- PostGIS extension may be unavailable in the sandbox; `apps/api/app/geo.py`
  includes a pure-SQL haversine fallback delivering equivalent results.
  Production deployment via `docker-compose.yml` always enables PostGIS +
  pgvector.
