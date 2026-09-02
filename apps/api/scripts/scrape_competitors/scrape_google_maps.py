"""Google Maps competitor scraper -> exact POI data as JSONL.

Searches Google Maps for real business/competitor listings and extracts the
exact detail a competitor mission needs: name, rating, review count, category,
full address, opening-hours state, coordinates and the source place URL.

Output is audit-friendly JSONL under ``data/scrape/`` and is NOT written to
the DB directly; ``ingest_google_maps.py`` imports those files into the
``businesses`` table with ``source="google_maps"``.

Usage
-----
    python -m scripts.scrape_competitors.scrape_google_maps            # all searches
    python -m scripts.scrape_competitors.scrape_google_maps --only restaurant
    python -m scripts.scrape_competitors.scrape_google_maps --details  # click-through for phone/website
    python -m scripts.scrape_competitors.scrape_google_maps --headful  # debug (real browser window)

Constraints
-----------
* Bounded, rate-respecting use (a few dozen queries), never for mass
  extraction and never CAPTCHA bypass infrastructure.
* Google Maps scraping is a Terms-of-Service gray area; keep runs small and
  space them out. Prefer the licensed Geoapify/Overpass sources for scale.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import math
import re
import sys
import time
import urllib.parse
from pathlib import Path

log = logging.getLogger("scrape.google_maps")

try:
    from playwright.sync_api import sync_playwright
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "playwright is not installed in the api venv: .venv/bin/pip install playwright "
        "(uses the system google-chrome, no browser download needed)"
    ) from e

OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "scrape" / "google_maps"


def _scrub(s: str | None) -> str | None:
    """Strip Google private-use glyphs (U+E000..U+F8FF) that render as random
    emojis (e.g. U+F54A → ❤) and would contaminate DB fields."""
    if not s:
        return s
    return "".join(ch for ch in s if not (0xE000 <= ord(ch) <= 0xF8FF)).strip()


BASE_URL = "https://www.google.com/maps/search/"

# ---------------------------------------------------------------------------
# Erode District Full Coverage Scraper — City → Town → Block/Village tiers
# ---------------------------------------------------------------------------
# Coverage tiers:
#   1. City (Erode): 30 categories × multiple queries = ~80 queries
#   2. Towns (11):   Key categories per town = ~100 queries
#   3. Blocks (14):  Essential categories per block = ~110 queries
# Total: ~290 queries × 20-40 results ≈ 6,000-12,000 businesses

# -- Tier 1: CITY (Erode city) — all categories, multiple query variants --
_CITY_CATEGORIES: list[tuple[str, list[str]]] = [
    ("restaurant", [
        "restaurants in Erode city",
        "best restaurants in Erode",
        "south indian restaurants in Erode",
        "non-veg restaurants in Erode",
        "veg restaurants in Erode",
    ]),
    ("fast_food", [
        "fast food in Erode",
        "fast food shops in Erode city",
        "biryani shops in Erode",
    ]),
    ("tea_shop", [
        "tea shops in Erode",
        "tea stalls in Erode city",
        "coffee shops in Erode",
    ]),
    ("bakery", [
        "bakeries in Erode",
        "cake shops in Erode",
        "bakery and sweets in Erode",
    ]),
    ("grocery", [
        "supermarkets in Erode",
        "grocery stores in Erode",
        "kirana stores in Erode",
        "departmental stores in Erode",
    ]),
    ("dairy", [
        "dairy shops in Erode",
        "milk booths in Erode",
        "poultry farms in Erode",
    ]),
    ("textile", [
        "textile shops in Erode",
        "tailors in Erode",
        "fabric stores in Erode",
    ]),
    ("clothing", [
        "clothing stores in Erode",
        "readymade shops in Erode",
        "garment shops in Erode",
    ]),
    ("electronics", [
        "electronics shops in Erode",
        "TV appliance stores in Erode",
    ]),
    ("mobile_shop", [
        "mobile phone shops in Erode",
        "mobile stores in Erode",
    ]),
    ("pharmacy", [
        "pharmacies in Erode",
        "medical stores in Erode",
    ]),
    ("hardware", [
        "hardware stores in Erode",
        "building materials in Erode",
        "cement dealers in Erode",
    ]),
    ("salon", [
        "beauty parlours in Erode",
        "hair salons in Erode",
    ]),
    ("food_processing", [
        "rice mills in Erode",
        "flour mills in Erode",
        "oil mills in Erode",
        "food processing units in Erode",
    ]),
    ("furniture", [
        "furniture shops in Erode",
        "furniture showrooms in Erode",
    ]),
    ("printing", [
        "printing shops in Erode",
        "photocopy shops in Erode",
    ]),
    ("stationery", [
        "stationery shops in Erode",
        "book stores in Erode",
    ]),
    ("fertilizer", [
        "fertilizer shops in Erode",
        "pesticide dealers in Erode",
    ]),
    ("seed_shop", ["seed shops in Erode"]),
    ("agricultural_equipment", [
        "agricultural equipment shops in Erode",
        "farm equipment dealers in Erode",
    ]),
    ("tractor_dealer", ["tractor dealers in Erode"]),
    ("animal_feed", ["animal feed shops in Erode"]),
    ("mechanic", [
        "bike mechanics in Erode",
        "car repair shops in Erode",
    ]),
    ("tyre_shop", ["tyre shops in Erode"]),
    ("auto_parts", ["auto spare parts shops in Erode"]),
    ("optical_shop", ["optical shops in Erode"]),
    ("sweet_shop", ["sweet shops in Erode"]),
    ("meat_shop", ["meat shops in Erode", "chicken shops in Erode"]),
    ("fruit_shop", ["fruit shops in Erode"]),
    ("vegetable_shop", ["vegetable shops in Erode", "vegetable market in Erode"]),
    ("hotel", ["hotels in Erode", "lodges in Erode"]),
    ("laundry", ["laundry shops in Erode"]),
    ("welding", ["welding shops in Erode"]),
    ("home_appliances", ["home appliance shops in Erode"]),
    ("computer_service", ["computer repair shops in Erode"]),
    ("photography", ["photography studios in Erode"]),
    ("veterinary", ["veterinary clinics in Erode"]),
]

# -- Tier 2: TOWNS — key categories per major town --
TOWNS: list[str] = [
    "Perundurai", "Bhavani", "Sathyamangalam", "Gobichettipalayam",
    "Anthiyur", "Nambiyur", "Modakkurichi", "Chennimalai",
]

TOWN_CATEGORIES: list[str] = [
    "restaurant", "grocery", "pharmacy", "textile", "electronics",
    "mobile_shop", "bakery", "tea_shop", "salon", "hardware",
    "furniture", "fertilizer", "mechanic", "sweet_shop",
]

# -- Tier 3: BLOCKS / VILLAGE CLUSTERS — essential categories per block --
BLOCKS: list[str] = [
    "Ammapet", "Anthiyur", "Bhavani", "Bhavanisagar", "Chennimalai",
    "Erode", "Gobichettipalayam", "Kodumudi", "Modakkurichi",
    "Nambiyur", "Perundurai", "Sathyamangalam", "Talavadi",
    "Thookanaickenpalayam",
]

BLOCK_CATEGORIES: list[str] = [
    "grocery", "restaurant", "pharmacy", "textile", "fertilizer",
]

# -- Tier 4: KEY VILLAGES with known market clusters --
KEY_VILLAGES: list[tuple[str, str]] = [
    # (village, block) — picked for population / market significance
    ("Boothapadi", "Ammapet"), ("Chennampatti", "Ammapet"),
    ("Guruvareddiyur", "Ammapet"), ("Kesaramangalam", "Ammapet"),
    ("Brammadesam", "Anthiyur"), ("Kuthampoondi", "Anthiyur"),
    ("Kavandapadi", "Bhavani"), ("Periyapuliyur", "Bhavani"),
    ("Thottipalayam", "Bhavani"), ("Mylambadi", "Bhavani"),
    ("Desipalayam", "Bhavanisagar"), ("Nallur", "Bhavanisagar"),
    ("Pungar", "Bhavanisagar"), ("Narasingapuram", "Chennimalai"),
    ("Perundurai", "Perundurai"), ("Thindal", "Erode"),
    ("Avalpoondurai", "Gobichettipalayam"),
    ("Bannari", "Sathyamangalam"), ("Olagadam", "Kodumudi"),
    ("Modakkurichi", "Modakkurichi"), ("Nambiyur", "Nambiyur"),
    ("Talavadi", "Talavadi"),
]

VILLAGE_CATEGORIES: list[str] = ["grocery", "pharmacy"]


def _build_searches() -> list[dict]:
    """Build the full three-tier search list."""
    searches: list[dict] = []

    # Tier 1: City (Erode)
    for cat, queries in _CITY_CATEGORIES:
        for q in queries:
            searches.append({"category_code": cat, "query": q, "tier": "city"})

    # Tier 2: Towns
    for town in TOWNS:
        for cat in TOWN_CATEGORIES:
            searches.append({
                "category_code": cat,
                "query": f"{cat.replace('_', ' ')} in {town}, Erode",
                "tier": "town",
            })

    # Tier 3: Blocks (village clusters)
    for block in BLOCKS:
        for cat in BLOCK_CATEGORIES:
            searches.append({
                "category_code": cat,
                "query": f"{cat.replace('_', ' ')} in {block}, Erode district",
                "tier": "block",
            })

    # Tier 4: Key villages
    for village, block in KEY_VILLAGES:
        for cat in VILLAGE_CATEGORIES:
            searches.append({
                "category_code": cat,
                "query": f"{cat.replace('_', ' ')} in {village}, {block}, Erode",
                "tier": "village",
            })

    return searches


SEARCHES: list[dict] = _build_searches()

# In-page JS that walks the search-results feed and pulls every listing card.
_EXTRACT_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const links = document.querySelectorAll('a[href*="/maps/place/"]');
  for (const a of links) {
    const href = a.href;
    if (seen.has(href)) continue;
    seen.add(href);
    // Nearest result card container that holds name + meta.
    let card = a;
    for (let i = 0; i < 6 && card; i++) {
      const t = (card.innerText || '').trim();
      if (t && (t.split('\n').length >= 2)) break;
      card = card.parentElement;
    }
    if (!card) card = a.parentElement || a;
    const text = (card.innerText || '').replace(/\n{2,}/g, '\n').trim();
    const name = (a.getAttribute('aria-label') || a.textContent || '').trim();
    const lat = href.match(/!3d(-?\d+\.\d+)/);
    const lng = href.match(/!4d(-?\d+\.\d+)/);
    const cidSeed = href.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/);
    const placeG = href.match(/16s%2F[gu]%2F([0-9a-zA-Z_]+)/);
    out.push({
      name,
      place_url: href.split('?')[0],
      cid_seed: cidSeed ? cidSeed[1] : null,
      google_id: placeG ? 'g/' + placeG[1] : null,
      latitude: lat ? parseFloat(lat[1]) : null,
      longitude: lng ? parseFloat(lng[1]) : null,
      raw_text: text,
    });
    // Data needs tabular containment; keep this small on purpose.
    if (out.length >= 120) break;
  }
  return out;
}
"""

# Best-effort parser for the card innerText produced by Google's SERP.
_PATT_RATING = re.compile(r'(\d\.\d)\s*\((\d[\d,]*(?:\.\d+[kKmM]?)?)\)|(\d\.\d)\s*stars?')
_PATT_OPEN = re.compile(r'\b(Open|Closed)\b.*', re.I)
_RATINGISH = re.compile(r'\d\.\d\s*(?:\(\d[\d,]*[kKmM]?\))?')
_REVIEWS_ONLY = re.compile(r'\(\d[\d,]*[kKmM]?\)')
_PLUS_CODE = re.compile(r'[0-9A-HJ-NP-Z]{6,8}\+[0-9A-HJ-NP-Z]{2}')


def _reviews_to_int(s: str) -> int | None:
    if not s:
        return None
    s = s.replace(",", "").strip().lower()
    try:
        if s.endswith("k"):
            return int(float(s[:-1]) * 1000)
        return int(float(s))
    except ValueError:
        return None


def _looks_like_address(s: str) -> bool:
    s = s.strip()
    if not s or len(s) < 4:
        return False
    if _REVIEWS_ONLY.fullmatch(s):  # "(59)" review count row
        return False
    if _RATINGISH.fullmatch(s):
        return False
    if "₹" in s or s.lower().startswith(("open", "closed")):
        return False
    return bool(_PLUS_CODE.search(s) or "," in s or re.search(r"\d", s))


def _parse_card(card: dict, category_code: str, queried_at: str) -> dict | None:
    """Turn a raw SERP card dict into a structured POI (best-effort).

    Google's SERP card text has a predictable scrawl:
      <name>
      4.6
      (1,234)
      South Indian restaurant · 7HFM+VM6, 80/1 Old Bus Stand Rd
      Open · Closes 11 pm
    but card layouts vary (rating inline as ``4.1(59) · ₹200-400``, no
    category shown, etc.). We skip rating/price/open rows and only ever emit
    plausible category + address tokens.
    """
    name = _scrub((card.get("name") or "").strip()) or ""
    if not name:
        return None
    text = card.get("raw_text") or ""

    rating = None
    reviews = None
    for m in _PATT_RATING.finditer(text):
        if m.group(1):
            rating = float(m.group(1))
            reviews = _reviews_to_int(m.group(2))
            break
        if m.group(3):
            rating = float(m.group(3))

    category = None
    address = None
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    for ln in lines:
        if not ln or ln == name or _RATINGISH.fullmatch(ln) or _REVIEWS_ONLY.fullmatch(ln):
            continue
        low = ln.lower()
        if low.startswith("★"):
            continue
        if "·" in ln and not low.startswith(("open", "closed")) and "₹" not in ln:
            parts = [p.strip() for p in ln.split("·") if p.strip()]
            if not parts:
                continue
            first = parts[0]
            if _RATINGISH.fullmatch(first) or _PLUS_CODE.fullmatch(first) or "₹" in first:
                continue  # rating/price-only row ("4.1(59) · ₹200-400")
            if category is None and len(first) > 1:
                category = _scrub(first)
                if len(parts) > 1:
                    rest = " · ".join(parts[1:]).strip()
                    if not _PLUS_CODE.fullmatch(rest):
                        address = _scrub(rest)
                break
        elif address is None and _looks_like_address(ln):
            address = _scrub(ln)

    if category is None:
        for ln in lines:
            if ln == name or _RATINGISH.fullmatch(ln) or _REVIEWS_ONLY.fullmatch(ln):
                continue
            if ln.lower().startswith(("open", "closed", "★")):
                continue
            if _PLUS_CODE.fullmatch(ln) or "₹" in ln or _looks_like_address(ln):
                continue
            category = _scrub(ln)
            break

    open_state = None
    open_m = _PATT_OPEN.search(text)
    if open_m:
        open_state = open_m.group(0)

    return {
        "source": "google_maps",
        "source_record_id": card.get("google_id") or card.get("cid_seed") or card.get("place_url"),
        "name": name,
        "normalized_name": name.lower().strip(),
        "category_code": category_code,
        "google_category": category,
        "latitude": card.get("latitude"),
        "longitude": card.get("longitude"),
        "address": address,
        "rating": rating,
        "review_count": reviews,
        "opening_hours_state": open_state,
        "place_url": card.get("place_url"),
        "cid_seed": card.get("cid_seed"),
        "google_id": card.get("google_id"),
        "queried_at": queried_at,
    }


def _extract_coords_from_url(poi: dict) -> dict:
    return poi


def scrape_search(browser, query: str, category_code: str, *, details: bool,
                  max_results: int = 60, headful: bool = False) -> list[dict]:
    """Run one Google Maps search and return structured POI dicts."""
    q = urllib.parse.quote(query)
    ctx = browser.new_context(
        locale="en-IN",
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()
    try:
        page.goto(f"{BASE_URL}{q}", timeout=45_000, wait_until="domcontentloaded")
        page.wait_for_selector('a[href*="/maps/place/"]', timeout=30_000)

        # Load more entries by scrolling the feed until stable / cap reached.
        for _ in range(12):
            n_before = page.evaluate("document.querySelectorAll('a[href*=\"/maps/place/\"]').length")
            if n_before >= max_results:
                break
            page.evaluate(
                "const f=document.querySelector('div[role=feed]');"
                "if(f){f.scrollTop=f.scrollHeight;}window.scrollBy(0,600);"
            )
            time.sleep(1.2)
            n_after = page.evaluate("document.querySelectorAll('a[href*=\"/maps/place/\"]').length")
            if n_after == n_before:
                time.sleep(2.0)  # one more chance before giving up scrolling
                n_after = page.evaluate("document.querySelectorAll('a[href*=\"/maps/place/\"]').length")
                if n_after == n_before:
                    break

        queried_at = dt.datetime.now(dt.timezone.utc).isoformat()
        raw = page.evaluate(_EXTRACT_JS)
        pois = []
        for c in raw:
            p = _parse_card(c, category_code, queried_at)
            if p is not None and p.get("latitude") is not None:
                pois.append(p)
        if pois:
            page.screenshot(path=f"{OUT_DIR / ('screen_' + category_code + '_' + str(len(pois)) + '.png')}", full_page=False)

        if details:
            pois = _enrich_details(page, pois)

        log.info("search=%r cat=%s pois=%d", query, category_code, len(pois))
        return pois
    finally:
        ctx.close()


def _enrich_details(page, pois: list[dict]) -> list[dict]:
    """Best-effort: open each place for phone / website. Slow; skips failures."""
    for poi in pois:
        url = poi.get("place_url")
        if not url:
            continue
        try:
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            phone = page.evaluate(
                "(() => { const a=document.querySelector('button[data-item-id*=phone]');"
                " return a ? (a.innerText||'').trim() : null; })()"
            )
            website = page.evaluate(
                "(() => { const a=document.querySelector('a[data-item-id*=authority]');"
                " return a ? (a.getAttribute('href')||a.innerText||'').trim() : null; })()"
            )
            if phone or website:
                poi["phone"] = phone
                poi["website"] = website
                log.info("detail %s -> phone=%s website=%s", poi.get("name"), bool(phone), bool(website))
            time.sleep(1.5)
        except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
            log.warning("detail parse failed for %s: %s", poi.get("name"), exc)
    return pois


def _write_jsonl(pois: list[dict], category_code: str, query: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    fname = OUT_DIR / f"{category_code}__{ts}__{urllib.parse.quote(query[:40])}.jsonl"
    with fname.open("w", encoding="utf-8") as fh:
        for p in pois:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    return fname


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Google Maps competitor scraper (JSONL)")
    ap.add_argument("--only", default=None, help="category_code filter (e.g. restaurant)")
    ap.add_argument("--tier", default=None, choices=["city", "town", "block", "village"],
                    help="limit to a specific coverage tier")
    ap.add_argument("--details", action="store_true", help="click through for phone/website")
    ap.add_argument("--headful", action="store_true", help="run with a visible browser")
    ap.add_argument("--max-results", type=int, default=60)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    searches = SEARCHES
    if args.only:
        searches = [s for s in searches if s["category_code"] == args.only]
    if args.tier:
        searches = [s for s in searches if s.get("tier") == args.tier]
    if not searches:
        ap.error(f"No searches matched filters: --only={args.only} --tier={args.tier}")

    # Deduplicate by (category_code, query) to avoid re-scraping
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for s in searches:
        key = (s["category_code"], s["query"])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    searches = unique

    log.info("=== Erode District Full Coverage Scrape ===")
    tier_counts: dict[str, int] = {}
    for s in searches:
        t = s.get("tier", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1
    for t in ["city", "town", "block", "village"]:
        if t in tier_counts:
            log.info("  Tier %-6s: %d searches", t, tier_counts[t])
    log.info("  Total:      %d searches", len(searches))

    all_pois: dict[str, list] = {s["category_code"]: [] for s in searches}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=not args.headful)
        try:
            for i, s in enumerate(searches):
                tier = s.get("tier", "?")
                log.info("[%d/%d] [%s] %s | %s", i + 1, len(searches), tier, s["category_code"], s["query"])
                try:
                    pois = scrape_search(
                        browser, s["query"], s["category_code"],
                        details=args.details, max_results=args.max_results, headful=args.headful,
                    )
                except Exception as exc:
                    log.warning("search failed: %s", exc)
                    pois = []
                if pois:
                    fname = _write_jsonl(pois, s["category_code"], s["query"])
                    all_pois[s["category_code"]].extend(pois)
                    log.info("  -> %d POIs written to %s", len(pois), fname.name)
                time.sleep(1.5)
        finally:
            browser.close()

    # Summary
    total = sum(len(v) for v in all_pois.values())
    by_cat = sorted(((k, len(v)) for k, v in all_pois.items()), key=lambda x: -x[1])
    log.info("=== SCRAPE COMPLETE ===")
    log.info("Total POIs: %d", total)
    for cat, n in by_cat:
        log.info("  %-25s %d", cat, n)

    # Merge all category JSONLs into a single file for easy ingest
    merged_path = OUT_DIR / f"erode_district_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')}.jsonl"
    with merged_path.open("w", encoding="utf-8") as fh:
        for cat_pois in all_pois.values():
            for p in cat_pois:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    log.info("Merged file: %s (%d lines)", merged_path, total)

    return 0


if __name__ == "__main__":
    sys.exit(main())