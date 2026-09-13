"""Adaptive Google Maps discovery — plateau detection, bounded, rate-respecting.

Replaces fixed 20-results / 12-scroll / fixed-query behavior with:
* configurable result ceiling + max scroll depth
* plateau detection (stop when new uniques plateau)
* dedup during discovery
* provenance + termination reason
* bounded concurrency, delays, retries, no CAPTCHA bypass
"""
from __future__ import annotations

import datetime as dt
import time
import urllib.parse

from app.discovery.config import CONFIG
from app.discovery.providers import DiscoveryObservation, DiscoveryResult
from app.discovery.targets import DiscoveryTarget

TERMINATION_REASONS = {
    "RESULT_PLATEAU": "RESULT_PLATEAU",
    "MAX_SCROLL_LIMIT": "MAX_SCROLL_LIMIT",
    "MAX_RESULT_LIMIT": "MAX_RESULT_LIMIT",
    "NO_MORE_RESULTS": "NO_MORE_RESULTS",
    "ERROR": "ERROR",
    "TIMEOUT": "TIMEOUT",
}

def _scrub(s: str | None) -> str | None:
    if not s:
        return s
    return "".join(ch for ch in s if not (0xE000 <= ord(ch) <= 0xF8FF)).strip()

# Reuse extractor from existing scraper for compatibility
try:
    from scripts.scrape_competitors.scrape_google_maps import _EXTRACT_JS, BASE_URL, _parse_card
except Exception:
    _EXTRACT_JS = r"""
    () => {
      const out=[]; const seen=new Set();
      const links=document.querySelectorAll('a[href*="/maps/place/"]');
      for(const a of links){ if(seen.has(a.href)) continue; seen.add(a.href);
        let card=a; for(let i=0;i<6&&card;i++){ const t=(card.innerText||'').trim(); if(t&&(t.split('\n').length>=2)) break; card=card.parentElement; }
        if(!card) card=a.parentElement||a; const text=(card.innerText||'').replace(/\n{2,}/g,'\n').trim();
        const name=(a.getAttribute('aria-label')||a.textContent||'').trim();
        const lat=a.href.match(/!3d(-?\d+\.\d+)/); const lng=a.href.match(/!4d(-?\d+\.\d+)/);
        const cidSeed=a.href.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/); const placeG=a.href.match(/16s%2F[gu]%2F([0-9a-zA-Z_]+)/);
        out.push({name, place_url:a.href.split('?')[0], cid_seed:cidSeed?cidSeed[1]:null, google_id:placeG?'g/'+placeG[1]:null, latitude:lat?parseFloat(lat[1]):null, longitude:lng?parseFloat(lng[1]):null, raw_text:text});
        if(out.length>=120) break;
      } return out;
    }
    """
    BASE_URL = "https://www.google.com/maps/search/"
    _parse_card = None

def scrape_target_adaptive(
    browser,
    target: DiscoveryTarget,
    max_results: int | None = None,
    max_scrolls: int | None = None,
    fast: bool = False,
) -> DiscoveryResult:
    """Run one search for a DiscoveryTarget with adaptive termination."""
    max_results = max_results or CONFIG.max_results_per_query
    max_scrolls = max_scrolls or CONFIG.max_scrolls
    # Tighten for village/rural to avoid explosion
    if target.locality_class in ("VILLAGE", "RURAL_LOCALITY"):
        max_results = min(max_results, 20)
        max_scrolls = min(max_scrolls, 5)

    q = urllib.parse.quote(target.query)
    ctx = browser.new_context(
        locale="en-IN",
        viewport={"width": 1024, "height": 768} if fast else {"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    )
    if fast:
        def _block(route):
            if route.request.resource_type in ("image", "stylesheet", "font", "media"):
                return route.abort()
            return route.continue_()
        ctx.route("**/*", _block)
    page = ctx.new_page()
    scrolls = 0
    unique_ids: set[str] = set()
    observations: list[DiscoveryObservation] = []
    termination = TERMINATION_REASONS["NO_MORE_RESULTS"]
    results_observed = 0
    start = time.time()
    sleep_base = 0.5 if fast else 1.2
    try:
        try:
            page.goto(f"{BASE_URL}{q}", timeout=CONFIG.timeout_s * 1000, wait_until="domcontentloaded")
            page.wait_for_selector('a[href*="/maps/place/"]', timeout=15_000)
        except Exception as e:
            return DiscoveryResult(
                query=target.query, category=target.category, target=target.to_dict(),
                observations=[], results_observed=0, unique_results=0,
                scrolls_attempted=0, queries_attempted=1, termination_reason=TERMINATION_REASONS["ERROR"] if "timeout" not in str(e).lower() else TERMINATION_REASONS["TIMEOUT"],
                elapsed_s=round(time.time() - start, 2),
            )
        # Adaptive scroll loop
        plateau_count = 0
        last_unique = 0
        for i in range(max_scrolls):
            scrolls = i + 1
            n_before = page.evaluate("document.querySelectorAll('a[href*=\"/maps/place/\"]').length")
            if n_before >= max_results:
                termination = TERMINATION_REASONS["MAX_RESULT_LIMIT"]
                break
            page.evaluate("const f=document.querySelector('div[role=feed]'); if(f){f.scrollTop=f.scrollHeight;} window.scrollBy(0,600);")
            time.sleep(sleep_base)
            n_after = page.evaluate("document.querySelectorAll('a[href*=\"/maps/place/\"]').length")
            # Deduplicate during discovery via href/ids
            raw = page.evaluate(_EXTRACT_JS)
            current_unique = len({r.get("google_id") or r.get("cid_seed") or r.get("place_url") for r in raw if r.get("place_url")})
            if current_unique >= max_results:
                termination = TERMINATION_REASONS["MAX_RESULT_LIMIT"]
                break
            new_count = current_unique - last_unique
            if new_count < CONFIG.plateau_min_new:
                plateau_count += 1
            else:
                plateau_count = 0
            last_unique = current_unique
            if plateau_count >= CONFIG.plateau_threshold:
                termination = TERMINATION_REASONS["RESULT_PLATEAU"]
                break
            if n_after == n_before:
                time.sleep(0.8 if fast else 2.0)
                n_after2 = page.evaluate("document.querySelectorAll('a[href*=\"/maps/place/\"]').length")
                if n_after2 == n_before:
                    termination = TERMINATION_REASONS["NO_MORE_RESULTS"]
                    break
            if scrolls >= max_scrolls:
                termination = TERMINATION_REASONS["MAX_SCROLL_LIMIT"]
                break

        # Extract & normalize after scrolling
        queried_at = dt.datetime.now(dt.timezone.utc).isoformat()
        raw = page.evaluate(_EXTRACT_JS)
        results_observed = len(raw)
        for card in raw:
            parsed = _parse_card(card, target.category, queried_at) if _parse_card else None
            if not parsed:
                # fallback minimal parse
                name = _scrub(card.get("name") or "")
                if not name or card.get("latitude") is None:
                    continue
                parsed = {
                    "source": "google_maps", "source_record_id": card.get("google_id") or card.get("cid_seed"),
                    "name": name, "normalized_name": name.lower().strip(), "category_code": target.category,
                    "latitude": card.get("latitude"), "longitude": card.get("longitude"),
                    "address": _scrub(card.get("raw_text","").split("\n")[-1] if card.get("raw_text") else None),
                    "place_url": card.get("place_url"), "cid_seed": card.get("cid_seed"), "google_id": card.get("google_id"),
                    "queried_at": queried_at,
                }
            sid = parsed.get("source_record_id") or parsed.get("google_id") or parsed.get("place_url")
            if sid in unique_ids:
                continue
            unique_ids.add(sid)
            if len(observations) >= max_results:
                break
            observations.append(DiscoveryObservation(
                source="google_maps",
                source_id=sid or "",
                name=parsed.get("name",""),
                normalized_name=parsed.get("normalized_name",""),
                category_code=target.category,
                latitude=parsed.get("latitude"),
                longitude=parsed.get("longitude"),
                address=parsed.get("address"),
                phone=parsed.get("phone"),
                website=parsed.get("website"),
                rating=parsed.get("rating"),
                review_count=parsed.get("review_count"),
                source_url=parsed.get("place_url"),
                retrieved_at=queried_at,
                query=target.query,
                target_locality=target.locality,
                target_category=target.category,
                provenance={"scraper": "google_maps_adaptive", "target": target.to_dict()},
            ))

        # Refine termination if we hit max results via dedup
        if len(observations) >= max_results and termination not in (TERMINATION_REASONS["MAX_RESULT_LIMIT"], TERMINATION_REASONS["RESULT_PLATEAU"]):
            termination = TERMINATION_REASONS["MAX_RESULT_LIMIT"]

        elapsed = round(time.time() - start, 2)
        return DiscoveryResult(
            query=target.query, category=target.category, target=target.to_dict(),
            observations=observations, results_observed=results_observed,
            unique_results=len(observations), scrolls_attempted=scrolls,
            queries_attempted=1, termination_reason=termination, elapsed_s=elapsed,
        )
    finally:
        ctx.close()
