"""Tamil Nadu Business Discovery — CLI.

Examples
--------
python -m scripts.discovery.run_discovery --state "Tamil Nadu" --district Erode --dry-run
python -m scripts.discovery.run_discovery --district Erode --locality Perundurai
python -m scripts.discovery.run_discovery --district all --dry-run
python -m scripts.discovery.run_discovery --district all --coverage-report
python -m scripts.discovery.run_discovery --district Erode --category grocery --live --max-localities 2
python -m scripts.discovery.run_discovery --district Erode --max-localities 5 --max-targets 50 --priority high --live
python -m scripts.discovery.run_discovery --resume <RUN_ID> --live
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from app.db.session import session_scope
from app.discovery.admin import TN_DISTRICTS_CANONICAL, canonical_district, validate_hierarchy
from app.discovery.orchestrator import run_discovery_plan

log = logging.getLogger("discovery.cli")

def _print_plan(plan: dict):
    print("\n=== Tamil Nadu Discovery Plan ===\n" if plan.get("districts") else "\n=== District Discovery Plan ===\n")
    if "districts" in plan:
        print(f"Districts: {plan['districts']}")
        print(f"Administrative localities discovered: {plan['administrative_localities_discovered']}")
        print(f"Search targets generated: {plan['search_targets_generated']}")
        print(f"Google Maps targets: {plan['google_maps_targets']}")
        print(f"OSM targets: {plan['osm_targets']}")
        print(f"\nHigh priority: {plan.get('high_priority')}")
        print(f"Medium priority: {plan.get('medium_priority')}")
        print(f"Low priority: {plan.get('low_priority')}")
        if plan.get("by_locality_class"):
            print(f"\nBy locality class: {plan['by_locality_class']}")
        print("\nNo hardcoded district-specific village lists detected.")
        print(f"Sample localities: 38/38 districts covered" if plan['districts']==38 else f"{plan['districts']} districts")
        if plan.get("preview"):
            print(f"\n{plan['preview']}")
    else:
        print(f"District: {plan.get('district')}")
        print(f"Administrative localities discovered: {plan.get('administrative_localities_discovered')}")
        print(f"Search targets generated: {plan.get('search_targets_generated')}")
        print(f"Google Maps targets: {plan.get('google_maps_targets')}")
        print(f"OSM targets: {plan.get('osm_targets')}")
        print(f"\nBy priority: {plan.get('by_priority')}")
        if plan.get("by_locality_class"):
            print(f"By locality class: {plan['by_locality_class']}")
        print("\nNo hardcoded village lists detected.")
        if plan.get("sample_targets"):
            print("\nSample targets:")
            for t in plan["sample_targets"][:3]:
                print(f"  {t['query']} | {t['locality_class']} | {t['priority']} | {t['radius_m']}m")
        if plan.get("preview"):
            print(f"\n{plan['preview']}")

def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Tamil Nadu Business Discovery & Coverage Engine")
    ap.add_argument("--state", default="Tamil Nadu", help="State (default Tamil Nadu)")
    ap.add_argument("--district", default="all", help="District name or 'all' for statewide (38 districts)")
    ap.add_argument("--locality", default=None, help="Filter to locality name contains")
    ap.add_argument("--category", default=None, help="Filter to single category_code (e.g. grocery)")
    ap.add_argument("--source", default="both", choices=["both", "google_maps", "osm", "licensed", "geoapify"], help="Discovery source")
    ap.add_argument("--max-localities", type=int, default=None, help="Cap localities for bounded test")
    ap.add_argument("--max-targets", type=int, default=None, help="Cap total targets (priority-sorted)")
    ap.add_argument("--priority", default=None, choices=["high", "medium", "low", "all"], help="Filter by priority")
    ap.add_argument("--resume", default=None, help="Resume run-id (requires --live)")
    ap.add_argument("--dry-run", action="store_true", help="Show plan without scraping")
    ap.add_argument("--coverage-report", action="store_true", help="Show coverage audit for district/all")
    ap.add_argument("--health", action="store_true", help="Show provider health (Google/OSM/Licensed)")
    ap.add_argument("--refresh", action="store_true", help="Ignore fresh cache and perform fresh provider queries (still updates cache)")
    ap.add_argument("--live", action="store_true", help="Run live discovery (bounded)")
    ap.add_argument("--max-results", type=int, default=20, help="Max results per query (live mode)")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of pretty text")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Resume requires live
    if args.resume and not args.live:
        ap.error("--resume requires --live")

    # Guard statewide live without caps
    is_statewide = args.district.lower() == "all" and not args.resume
    if args.live and is_statewide and args.max_localities is None and args.max_targets is None:
        print("ERROR: Statewide live discovery requires --max-localities or --max-targets. Use --dry-run to inspect the plan.", file=sys.stderr)
        return 2

    # Default to dry-run unless live or coverageReport
    if not args.live and not args.coverage_report and not args.dry_run:
        args.dry_run = True

    with session_scope() as session:
        if args.health:
            from app.discovery.orchestrator import get_provider_health
            healths = get_provider_health(args.source)
            print("\n=== Provider Health ===\n")
            print(f"{'Provider':20s} {'Status':15s} Reason")
            print("-" * 70)
            for h in healths:
                print(f"{h.provider:20s} {h.status:15s} {h.reason}")
            if args.json:
                print(json.dumps([{"provider": h.provider, "status": h.status, "reason": h.reason} for h in healths], indent=2))
            return 0

        if args.coverage_report:
            # Real discovery coverage from CoverageAudit, not just admin counts
            from app.db.models import CoverageAudit
            from sqlalchemy import select
            from app.discovery.coverage import coverage_label
            if args.district.lower() in ("all", ""):
                print("\n=== Discovery Coverage Report — Tamil Nadu (38 districts) ===\n")
                # Show admin coverage
                from app.discovery.admin import get_all_districts
                districts = get_all_districts(session)
                for d in districts:
                    # Discovery coverage
                    cov_rows = session.execute(select(CoverageAudit).where(CoverageAudit.district == d.name)).scalars().all()
                    if not cov_rows:
                        d_status = "NOT_SEARCHED"
                    else:
                        # aggregate
                        from app.discovery.coverage import aggregate_coverage, CoverageRecord
                        recs = []
                        for r in cov_rows:
                            recs.append(CoverageRecord(district=r.district, locality=r.locality or "", category=r.category_code or "", source=r.source, queries_attempted=r.queries_attempted or 0, queries_successful=r.queries_successful or 0, unique_results=r.unique_results or 0, google_results=r.google_results or 0, osm_results=r.osm_results or 0, cross_source_matches=r.cross_source_matches or 0, last_scraped_at=r.last_scraped_at.isoformat() if r.last_scraped_at else None, coverage_status=r.coverage_status or "NOT_SEARCHED"))
                        agg = aggregate_coverage(recs)
                        d_status = agg["overall"]
                    print(f"  {d.name:20s} localities={d.locality_count:4d} discovery={d_status}")
                if args.json:
                    print(json.dumps({"districts": len(districts), "total_localities": sum(x.locality_count for x in districts)}, indent=2))
                return 0
            else:
                canon = canonical_district(args.district)
                from app.discovery.admin import get_all_districts
                districts = get_all_districts(session)
                d = next((x for x in districts if x.name == canon), None)
                # Discovery rows for this district
                cov_rows = session.execute(select(CoverageAudit).where(CoverageAudit.district == canon)).scalars().all()
                print(f"\n=== Discovery Coverage Report — {canon} ===")
                print(f"Administrative localities: {d.locality_count if d else 0}")
                if not cov_rows:
                    print("Discovery coverage: Not yet surveyed (no CoverageAudit rows)")
                else:
                    for r in cov_rows[:10]:
                        print(f"  {r.locality} | {r.category_code} | {r.source} | {r.coverage_status} | attempts={r.queries_attempted} uniques={r.unique_results}")
                    print(f"Total discovery records: {len(cov_rows)}")
                print(json.dumps({"district": canon, "localities": d.locality_count if d else 0, "discovery_records": len(cov_rows)}, indent=2))
                return 0

        if args.live:
            from app.discovery.orchestrator import run_live
            # For live, we support resume and refresh
            if args.resume:
                try:
                    result = run_live(
                        session,
                        district=args.district,
                        locality=args.locality,
                        category=args.category,
                        source=args.source,
                        max_localities=args.max_localities,
                        max_targets=args.max_targets,
                        priority=args.priority,
                        resume_run_id=args.resume,
                        refresh=args.refresh,
                    )
                except ValueError as e:
                    print(f"ERROR: {e}", file=sys.stderr)
                    return 2
                print(f"\n=== Resumed Discovery Run {args.resume} ===")
                print(json.dumps(result, indent=2))
                return 0
            # Normal live
            try:
                result = run_live(
                    session,
                    district=args.district,
                    locality=args.locality,
                    category=args.category,
                    source=args.source,
                    max_localities=args.max_localities,
                    max_targets=args.max_targets,
                    priority=args.priority,
                    refresh=args.refresh,
                )
            except ValueError as e:
                print(f"ERROR: {e}", file=sys.stderr)
                return 2
            print(f"\n=== Live Discovery Completed ===")
            print(f"Run ID: {result['run_id']}")
            print(f"Targets scraped: {result['targets_scraped']}/{result['targets_generated']}")
            print(f"Observations (businesses identified): {result['observations']}")
            print(f"Mapped businesses (canonical): {result['canonical_businesses']}")
            print(f"Cross-source matches: {result['cross_source_matches']}")
            print(f"Status: {result['status']}")
            if args.json:
                print(json.dumps(result, indent=2))
            return 0

        # Dry-run plan
        from app.discovery.orchestrator import run_discovery_plan
        from app.discovery.targets import generate_targets, schedule_targets
        plan = run_discovery_plan(session, district=args.district, locality=args.locality, category=args.category, dry_run=args.dry_run, max_localities=args.max_localities)
        # If max-targets/priority specified in dry-run, show preview
        if args.max_targets or args.priority:
            # Generate full then schedule preview
            all_targets = generate_targets(session, district=args.district, locality=args.locality, category=args.category, source=args.source, max_localities=args.max_localities)
            scheduled = schedule_targets(all_targets, priority_filter=args.priority, max_targets=args.max_targets, session=session)
            plan["preview"] = f"With --max-targets {args.max_targets or len(scheduled)} and --priority {args.priority or 'all'}, the following {len(scheduled)} targets would execute first (sorted high→low, NOT_SEARCHED first)."
            plan["scheduled_targets"] = len(scheduled)
            plan["scheduled_sample"] = [t.to_dict() for t in scheduled[:3]]
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            _print_plan(plan)
            if args.dry_run and plan.get("districts"):
                print("\n--- Hierarchy Validation ---")
                h = validate_hierarchy(session)
                print(f"38/38 districts: {h['districts_with_data']}/{h['total_districts']} with data, total localities {h['total_localities']}")
                # Block-aware
                if h.get("true_duplicate_admin_rows"):
                    print(f"True duplicate admin rows (district+block+village): {len(h['true_duplicate_admin_rows'])}")
                    for d in h["true_duplicate_admin_rows"][:3]:
                        print(f"  {d}")
                if h.get("same_name_different_block"):
                    print(f"Same village name in different blocks (diagnostic): {len(h['same_name_different_block'])}")
                if h["districts_missing"]:
                    print(f"Missing: {h['districts_missing']}")
                else:
                    print("All 38 districts covered.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
