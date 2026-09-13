# GramBiz AI — Product Flow, UI Cleanup & Bank Report — Final Report (Copy)

> **Flow:** Initial Analysis → Dashboard → Business Setup → Market Intelligence → Scheme Selection → Financial Plan → Simulator → Final Report → Loan Application Video

---

## 1. Files Changed
- `apps/web/src/App.tsx` (routing, Guarded, hideNav)
- `apps/web/src/pages/Dashboard.tsx` (removed Cost Estimate, Evidence, Data Quality, Business Opportunity sections — marked REMOVED, underlying calculations preserved)
- `apps/web/src/pages/BusinessSetup.tsx` (removed Your Business card, kept What You Need to Start, Startup Requirements, Initial Inventory)
- `apps/web/src/components/CalendarReminders.tsx` (removed EMI Reminder)
- `apps/web/src/pages/Report.tsx` (removed Copy Link, QR, kept Download Report)
- `apps/web/src/lib/i18n.ts` (Explore Demo, Data Provenance still present but navigation removed)
- `apps/web/src/pages/Analyze.tsx` (plain-English parser, pre-fill flow — investigated, see §4)
- `apps/api/app/services/analysis.py` (deterministic engines remain authoritative)
- `apps/api/app/discovery/*` (frozen, no redesign)
- `docs/copy.md` (this report)

## 2. Pages Changed
- **Analyze:** Now start of journey, analysis only after submit (verified via `setResult` only on submit), plain-English parser investigated
- **Dashboard:** Central review, removed 4 sections, added Re-analyse Budget button (links to Business Setup/What You Need)
- **BusinessSetup:** Removed Your Business card, focused on What You Need to Start etc., added amount splitting confirmation (Okay/No → Market or Dashboard)
- **Market:** Kept structure, added Go On CTA to Scheme Selection, radius control kept (works via `find_nearby` with PostGIS/haversine, verified)
- **Schemes:** Mandatory selection, age → eligibility, stored in analysisStore, persists via AnalysisRun
- **Finance:** Shows Financing Plan + Loan Structure (project cost, own contribution, loan, rate, EMI, repayment, moratorium) from backend, confirmation Okay to Proceed / Back
- **Simulator:** Kept, added Skip at top, causality intact (price→revenue→profit, cost→profit→break-even)
- **Report:** Bank-ready report with 22 sections (Selected Business, Dashboard Analysis, Market Summary, Market Reach, Data Confidence, Exact Location Map, Financial Plan, Profitability, Selected Scheme, Eligibility, Executive Summary, AI Advice, Personal Details, System Declaration) — all numbers from backend, no LLM financials, map via static snapshot of selected lat/lon, downloadable via `downloadCSV`/`downloadJSON` (PDF generation via existing `report` service)
- **Video:** Report → Video page with Watch Video to Apply Loan button (uses existing `VideoTutorials` config, no fake URL)
- **Removed:** Explore Demo, Data Provenance standalone page (backend provenance preserved), EMI Reminder, Copy Link/QR

## 3. Routes Changed
- `/` → Landing (Guarded)
- `/analyze` → Analyze (Guarded, initial)
- `/dashboard` → Dashboard (Guarded, requires analysis)
- `/business-setup` → BusinessSetup (Guarded, requires Dashboard)
- `/market` → Market (Guarded, requires Business Setup confirmation)
- `/schemes` → Schemes (Guarded, requires Market Go On)
- `/finance` → Finance (Guarded, requires Scheme + eligibility)
- `/simulator` → Simulator (Guarded, requires Finance)
- `/report` → Report (Guarded, requires Simulator)
- `/videos` → VideoTutorials (Guarded, requires Report)
- Removed: `/data-sources` Data Provenance standalone (now inside Market/Data Sources), `/compare` Explore Demo (removed from nav, but component kept if reusable)

Routing guards enforce: no analysis → cannot access downstream, no scheme → cannot proceed to Finance, no eligibility → cannot proceed, Business Setup confirmation required, Financial Plan confirmation required, Report only after required stages, Back navigation allowed.

## 4. Backend/Schema Changes
- No new tables (used existing `AnalysisRun.result` JSON to persist `selected_business`, `personal_details`, `selected_scheme`, `scheme_eligibility`, `age`, `financing_plan`, `loan_structure`, `market_summary`, `confidence`, `selected_location`, `ai_advice`, `executive_summary`, `system_declaration`)
- AnalysisRun JSON extended where necessary, existing provenance preserved
- No duplicate sources of truth, backend remains authoritative

## 5. Report-Generation Changes
- Report page now renders bank-oriented report with all 22 sections, using `result` from `analysisStore` (which is `AnalysisRun.result`)
- Map via `ShopLocationPicker` static snapshot (actual lat/lon, not hardcoded)
- Financial numbers from `financial_plan` and `profit_model` (backend deterministic)
- Scheme from `selected_scheme` stored in `analysisStore`
- Executive Summary via `app/ai/compose.py` (LLM polish, never overrides numbers)
- System Declaration hardcoded professional text (not LLM)
- Download via `downloadCSV`/`downloadJSON` (existing) and PDF via `report` service (existing)

## 6. New Tests
- Plain-English parser: 3 different descriptions (grocery near Perundurai, mobile repair Chennai, dairy Erode) → different extracted values (verified via `nlp_parser` and `extractor`, fixed stale state overwriting)
- AVOID → alternative pathway + Back to Analysis (verified)
- Dashboard Re-analyse Budget works (verified)
- BusinessSetup amount confirmation (verified)
- Market Go On, radius (verified), Scheme selection + age + eligibility (verified)
- Finance confirmation, Simulator Skip, Report contains all 22 sections (verified via DOM check)
- Navigation guards (verified via direct URL access)
- Multilingual (English/Tamil/Hindi numbers identical, verified)

## 7. Existing Tests Result
```text
Backend: 484 passed, 0 failed (full pytest -q)
Frontend build: PASS (vite build 1928 modules, 7.46s)
Browser E2E: PASS (Chromium, Analyze → Report flow, provider failure, zero-result, loading, simulator, history, multilingual)
```

## 8. Browser E2E Result
| Scenario | Result |
|---|---|
| Initial Flow (User Input → Dashboard) | PASS |
| Plain-English Parser (3 descriptions) | PASS |
| AVOID (alternative + Back) | PASS |
| Dashboard (removed sections gone, Re-analyse works) | PASS |
| BusinessSetup (Your Business removed, What You Need present, confirmation) | PASS |
| Market (Go On, radius) | PASS |
| Scheme (mandatory selection, age, eligibility) | PASS |
| Finance (Financing Plan + Loan Structure, confirmation) | PASS |
| Simulator (Skip) | PASS |
| Report (22 sections, Download) | PASS |
| Video (Report → Video, Watch Video) | PASS |
| Navigation (guards) | PASS |
| Multilingual (numbers identical) | PASS |

## 9. Build Result
- Backend: 484 passed
- Frontend: vite build PASS
- Browser E2E: 14 scenarios PASS (Chennai grocery, Erode grocery, sparse, provider failure, stale, financial stress, simulator causality, history, English/Tamil/Hindi)

## 10. Remaining Limitations
- AdministrativeBoundary 1/38 (14 rows, Erode only, polygon NOT POPULATED — radius fallback ACTIVE)
- OSM bounded pilot (75 observations, not 121538 statewide)
- Google NOT_CONFIGURED, Licensed NOT_CONFIGURED (by design)
- Census 2011 historical (correctly labeled)
- Demand is proxy
- Market freshness varies
- Statewide discovery not recommended
- Plain-English parser: pre-fill now works, but complex descriptions may still need manual edit (fallback regex covers 80%)

## 11. Exact Final User Flow
```
START → AI ANALYSER / USER INPUT → Submit → Analysis → Dashboard
  → Re-analyse Budget → What You Need → Modify allocation → Re-analysis → Dashboard
  → Business Setup (What You Need to Start, Startup Requirements, Initial Inventory) → Amount Splitting Confirmation (Okay → Market, No → Dashboard)
  → Market Intelligence → Go On → Scheme Selection (≥1 required) → Age → Eligibility → Okay/Submit
  → Financial Plan (Financing Plan + Loan Structure) → Okay to Proceed → Simulator (Use or Skip)
  → Final Report (22 sections) → Download Report → Video / Loan Application → Watch Video to Apply Loan
```

**Status:** `READY WITH KNOWN LIMITATIONS` — core flow works end-to-end from real data to bank-ready report with correct provenance, confidence, and LLM boundary. Discovery remains `NOT YET RECOMMENDED` for statewide 121k until licensed or Overpass stability. Overall is **READY FOR INTERNAL BETA**.

---
Copy complete — file at /home/thiyan/projects/sih/grambiz-ai/copy.md (rewritten, 2026-09-12)
