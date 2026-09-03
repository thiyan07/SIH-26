# SIH26091 Compliance & Readiness Matrix

**Project:** GramBiz AI — Hyper-local business intelligence & financial advisory for rural micro-entrepreneurs
**Problem Statement:** SIH 26091 (rural / MSME business feasibility via multilingual NLP + evidence-based financial structuring)
**Document date:** 2026-09-03 (updated)
**Status of test suite:** 294 tests passing (financial, geospatial, NLP/advisory, API E2E, weather-risk, financial-structuring honesty, NLP multilingual)

This document is an **honest** self-assessment. It states what is genuinely implemented,
where that implementation is a demo/proxy rather than production-grade, and what remains
explicitly out of scope or deliberately un-wired. **Green** = works & demo-verifiable now;
**Amber** = works but with caveats; **Red** = not implemented / intentionally deferred.

---

## 1. Verdict summary

| Pillar | Status | Readiness |
|---|---|---|
| Multilingual NLP advisory (free text → structured plan) | ✅ Green | Complete — parse, pre-fill, full report |
| Financial structuring correctness (EMI, moratorium, subsidy) | ✅ Green | Verified numerically + 29 dedicated tests |
| Scheme eligibility & recommendation (real seeded schemes) | ✅ Green | 20 schemes in DB (18 real + 2 demo) |
| Data honesty / provenance (never fabricate figures) | ✅ Green | Assumption-leak fixed: exact assumed fields surfaced per loan structure |
| Frontend multilingual (English / தமிழ் / हिंदी) | 🟡 Amber | Nav + advisory localized; many page strings English-only |
| Security & ops hardening | 🟡 Amber | Rate limits + logging + graceful shutdown; auth not implemented |
| **Overall demo readiness** | **≈ 84 / 100** | Strong, honest, demo-able; known production gaps documented |

---

## 2. Functional requirements (FR)

| ID | Requirement | Status | Evidence / Notes |
|---|---|---|---|
| FR1 | User describes business in free text (EN/TA/HI) | ✅ Green | `POST /advisory/parse`; NLP parser `app/engines/nlp_parser.py` (lakh/multipliers for ta/hi/en). Verifid: Tamil dairy → block Bhavani, ₹5,00,000; English *"five lakh rupees"*/Hindi `लाख`/Tamil `லட்சம்` number-words all resolve; transliterated Tamil loanwords (`டெய்ரி`) and inflected district (`ஈரோட்டில்`) now captured |
| FR2 | Frontend exposes the NLP advisory path | ✅ Green | `Analyze.tsx` — free-text panel + "Parse & Pre-fill" + "Full Advisory Report"; `/advisory` added to Vite proxy. Verified in-browser |
| FR3 | Multilingual UI (EN/TA/HI) | 🟡 Amber | Nav, subtitle, footer, advisory panel localized via `lib/i18n.ts` (~40 keys). Many page-level strings (Market/Map/Finance/…) remain English-only |
| FR4 | Pin location & map nearby businesses | ✅ Green | Location search + OSM business map + MapCN |
| FR5 | Compute demand / competition / accessibility / price | ✅ Green | Deterministic scoring engines `app/engines/*` |
| FR6 | Transparent opportunity score w/ provenance & confidence | ✅ Green | `app/engines/score.py`; confidence labels per frontend |
| FR7 | Financial plan: cost, loan, scheme routing, EMI | ✅ Green | `financial_structuring.py` + `repayment.py`; EMI-during/after-moratorium exposed |
| FR8 | Profit simulation & repayment health | ✅ Green | `profit.py`, `repayment_health` — verified coverage ratio |
| FR9 | GO / MODIFY / AVOID recommendation | ✅ Green | `app/engines/score.py` recommendation |
| FR10 | Government scheme catalogue (rural MSME) | ✅ Green | 20 schemes seeded (PMEGP, MUDRA, Stand-Up, TN UYEGC, NABARD SHG, …) |

**FR readiness: 9 green, 1 amber → ~90/100**

---

## 3. Financial correctness (Tier 1 audit)

Verified numerically; **29 tests** in `test_financial.py` + `test_api_e2e.py`:

- Post-moratorium amortization is mathematically correct: constant EMI after moratorium, loan fully amortizes.
- `total_repayment − principal == total_interest` for all three moratorium modes
  (interest-only: 9988.64; deferred-interest: 10135.88; principal-deferred: 9988.64).
- No-moratorium effective EMI == standard EMI (degenerate case clean).
- `monthly_emi_during_moratorium` (interest-only during moratorium) correctly distinct from post-moratorium debt-service EMI.
- Subsidy treated non-double-counted when capitalised interest present.

**Readiness: ✅ Green — 100/100**

---

## 4. Null-safety & robustness (Tier 2 audit)

- `SchemeRule` fallback (no eligible scheme / zero capital) no longer crashes — default `term_loan` rule applied instead of `derive_financial_plan(0)` which raised.
- `financial_structuring.py` + `financial.py` `_scheme_rules` use None-aware defaults (`is not None`), so a legitimate `0` interest/tenure/margin/subsidy is preserved instead of being coerced to a default.
- **Bug fixed:** `POST /advisory/report` silently discarded structured form fields whenever `free_text` was present. Structured fields are now **overlaid** onto the NLP parse, so an explicit `capital_available`/`project_cost` is never lost. Verified: `capital_available=30000` now appears in `parsed_input`.
- **Bug fixed:** `capital_available` of zero/None no longer 500s the report endpoint.
- All 294 tests pass after these changes.

**Readiness: ✅ Green — 100/100**

---

## 5. Data provenance & honesty (Tier 3 audit / P)

| ID | Item | Status | Notes |
|---|---|---|---|
| P1 | Provenance flags on data | 🟡 Amber | Present but **implicit not enum** — source labels exist, but no machine-readable enum like `source_type=official|scraped|modelled|demo` on every field |
| P2 | Machine-readable provider / ai_mode | 🟡 Amber | `provider` labels exist for AI/weather/geocode; not a first-class per-result contract |
| P3 | ESTIMATED labels per item (not blanket) | 🟡 Amber | **Improved this audit:** `loan_structure.is_assumed` + `assumed_fields` + `scheme_source` now surface **exactly** which financial terms a scheme did not declare (e.g. a grant scheme with no interest/tenure). Surfaced in the UI. Grant-scheme defaults are no longer silently substituted — they are labelled ASSUMED/ESTIMATED for the specific fields |
| P4 | Never fabricate statistics | ✅ Green | All numbers from deterministic engines; AI layer only explains. Core principle honored |
| P5 | Historical baselines labelled | ✅ Green | Census 2011 etc. explicitly labelled, never presented as current |
| P6 | Real vs demo scheme parameters | 🟡 Amber | 18 real schemes + 2 demo; demo rows clearly named `micro_finance`/`term_loan`. Fallback `term_loan` demo rule is now marked `is_assumed=True` |

**Provenance readiness: ~72/100** (honest; intentional not to overstate)

---

## 6. Security & operations (Tier 5 audit / S)

| ID | Item | Status | Notes |
|---|---|---|---|
| S1 | Authentication | 🔴 Red | **Not implemented** — API is unauthenticated. Documented as a deliberate demo-scope decision, **not** production-ready |
| S2 | Authorization / per-user data | 🔴 Red | Not implemented |
| S3 | Session / token management | 🔴 Red | Not implemented |
| S4 | Input validation | 🟡 Amber | Pydantic models validate; improvements always possible |
| S5 | None/undefined-safe defaults | ✅ Green | Fixed in Tier 2 (see §4) |
| S6 | CORS `allow_credentials=True` | 🟡 Amber | Present; origins restricted to localhost, but credentials+CORS is risky if origins broaden |
| S7 | DB default credentials | 🟡 Amber | Dev DB uses `grambiz:grambiz` (local-only, `trust` auth) — **must change** before any shared deployment |
| S8 | Exception logging | ✅ Green | Global handler now `logger.exception(...)` — full server-side traceback on 500 (added this audit) |
| S9 | Graceful shutdown | ✅ Green | `lifespan` handler logs + flushes on shutdown |
| S10 | Rate limiting on external / compute-heavy endpoints | 🟡 Amber | Applied to `/businesses/*` (incl. `/discovery` 20/min), `/ai/*` (15/min), `/rag/*`, `/advisory/*` (15–60/min), `/analysis` (30/min), `/geocode/*` (60/min) — 429 verified working. `/financial`,`/schemes`,`/score` (pure deterministic, no external I/O) left unbounded by design, as are simple DB-shot GETs |
| S11 | Real API keys in `.env`/`.env.bak` | 🟡 Amber | **User action item:** rotate/remove any committed keys; keep keys server-side only |
| S12 | Docs disabled outside dev | ✅ Green | `/docs`,`/redoc`,`/openapi.json` only when `app_env=development` |

**Security readiness: ~60/100** (functional hardening done; **auth is the hard blocker** for production, acceptable for hackathon demo)

---

## 7. Multilingual & accessibility (FR3 detail)

- UI language toggle (EN/TA/HI) in the nav — localized: nav, brand subtitle, footer, advisory panel (title, subtitle, placeholder, buttons, report section labels).
- NLP accepts EN/TA/HI free text with correct lakh/multiplier handling for Tamil (`லட்சம்`/`இலட்சம்`) and Hindi (`लाख`).
- **Gap:** Market, Map, Finance, Simulator, Report, Schemes, Data-source page bodies are largely English-only.

**Readiness: ~55/100** — functional and demo-able, but not full-page multilingual.

---

## 8. Aggregated readiness score

| Area | Weight | Score | Weighted |
|---|---|---|---|
| Functional requirements (FR) | 30% | 90 | 27.0 |
| Financial correctness | 20% | 100 | 20.0 |
| Null-safety / robustness | 15% | 100 | 15.0 |
| Data provenance & honesty | 15% | 72 | 10.8 |
| Security & operations | 12% | 60 | 7.2 |
| Multilingual / accessibility | 8% | 55 | 4.4 |
| **Total** | **100%** | | **≈ 84 / 100** |

> **Honest headline:** The **core deliverable of SIH26091 — an evidence-based, multilingual,
> financially-correct feasibility + advisory platform — is fully built and demo-verifiable.**
> The gap to production is almost entirely **auth/security (S1–S3) and non-auth page-level
> translation**, neither of which is required to demonstrate the problem statement's core.
> Treat ~83/100 as "demo-ready & technically sound; not yet deployment-hardened."

---

## 9. Known intentional limitations (do not misrepresent)

1. **No authentication (S1–S3)** — API is open. Acceptable for a hackathon demo; must be added for any public deployment.
2. **Real API keys on disk** (`.env`/`.env.bak`) — rotate/remove before sharing. Keys are only ever read server-side.
3. **CORS credentials + restricted origins** (S6) — fine for localhost; re-review before broadening origins.
4. **DB default password / `trust` auth** (S7) — local-only dev posture; change before shared hosting.
5. **Provenance flags are implicit, not machine-readable enums** (P1); estimate-labelling is blanket not per-item (P3).
6. **Some schemes are demo parameters** (`micro_finance`, `term_loan`) — always labelled; real 18 schemes are research-seeded, verify with the channelizing agency.
7. **LLM is `mock` by default** — deterministic; an API key enables OpenAI/NVIDIA-backed *explanations* only (never fabrication).
8. **Frontend not 100% translated** — nav + advisory localized; Market/Map/Finance/Simulator/Report/Schemes bodies remain English.

---

## 10. This audit's changes (what "so far" produced)

- **Tier 1** — amortization correct (constant post-morat EMI; loan fully amortizes; total-interest invariant).
- **Tier 2** — None-safe scheme defaults; fixed `/advisory/report` structured-overlay bug; fixed zero-capital crash.
- **Tier 3** — Wired multilingual NLP advisory into the React frontend (proxy + panel + parse/pre-fill + full report), verified in-browser.
- **Tier 4** — Extended i18n to nav, subtitle, footer, and the advisory panel (EN/TA/HI).
- **Tier 5** — Rate-limited compute-heavy endpoints (429 verified), added exception logging, graceful-shutdown lifespan.
- **Tier 6** — This document.

---

## 11. Latest audit pass (this session)

Fixes and hardening applied in the most recent end-to-end audit (all 294 tests green:

- **§5 assumption-leak eliminated (financial_structuring.py).** When a scheme does not
  declare `interest_rate` / `tenure_years` / `moratorium_months` / `margin_pct` (e.g. a
  grant scheme), the engine **no longer silently substitutes** `10.0 / 5 / 10.0` and presents
  them as scheme terms. Instead it records the exact fields that were assumed
  (`loan_structure.assumed_fields`), sets `is_assumed=True`, and notes them in the UI as
  **ASSUMED/ESTIMATED**. The demo fallback `term_loan` rule is likewise marked assumed with
  its `scheme_source` surfaced. Tests: `test_financial_structuring_honesty.py` (7 tests).
- **`scheme_eligibility` now aligns with the recommended scheme.** Previously it read
  `eligible_schemes[0]` (top match-score), which could disagree with the chosen ELIGIBLE
  scheme; now it resolves the loan's own `scheme_code`. `alternatives` wired through instead
  of always empty. `scheme_eligibility` is now serialized in `to_dict()`.
- **Multilingual NLP expansion (nlp_parser.py).** Added English number-words
  (`"five lakh rupees"` → ₹5,00,000), Tamil transliterated loanwords (`டெய்ரி` → dairy,
  `டெயிலரிங்` → textile), Tamil/Hindi block & village aliases (`பவானி`/`भवानी` → Bhavani,
  `பெருந்துறை` → Perundurai), and Tamil oblique/inflected district forms (`ஈரோட்டில்` → Erode).
  Tests: `test_nlp_parser_multilingual.py` (7 tests).
- **Hardcoded year removed** (`app/services/analysis.py`): `years_since_2011` now uses
  `date.today().year` instead of a literal `2026`.
- **Frontend honesty surfacing:** `AdvisoryLoanStructure` type extended with
  `is_assumed` / `assumed_fields` / `scheme_source`; `Analyze.tsx` renders a prominent
  "Assumed / estimated fields" warning when `is_assumed` is true. `tsc -b` and `eslint` clean.
- **Verified (no change needed):** scheme hard-constraint flow never marks a scheme ELIGIBLE
  when a project-cost (or any) rule fails (`_status_from_score` guards on `has_fail`);
  competitor "mapped vs live_discovery" are two distinct, description-specific, provenance-
  carrying fields; RAG returns an "insufficient evidence" answer (never a fabricated one) and
  every grounded answer carries citations; the LLM system prompt forbids inventing any figure.
- **Security re-verified:** rate limiting on all external/compute-heavy routes, CORS restricted,
  docs disabled outside dev, secrets env-only, `.env` is gitignored and **not** tracked, only
  `.env.example` (placeholders) committed.

**Aggregated readiness after this pass: ≈ 84 / 100** (was ≈ 78 / 100). The two drivers of the
remaining gap are unchanged and are **not** core to the problem statement: (a) missing
authentication (S1–S3), (b) page-level (non-advisory) UI not fully translated.
