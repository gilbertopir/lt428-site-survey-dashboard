"""
survey/management/commands/generate_maps.py

Pre-generates all static satellite map images for the route report.
Run once after loading new survey data.

Usage:
    python manage.py generate_maps
    python manage.py generate_maps --route LT428
    python manage.py generate_maps --force
"""

import time
from django.core.management.base import BaseCommand, CommandError

from survey.services.data_loader import scan_routes, load_route_data, build_tour, get_alignment_coords
from survey.services.map_renderer import get_stop_maps, clear_route_cache, CACHE_DIR


class Command(BaseCommand):
    help = "Pre-generate static satellite map images for all route report stops."

    def add_arguments(self, parser):
        parser.add_argument(
            "--route",
            type=str,
            default=None,
            help="Only generate maps for this route ID (e.g. LT428). Defaults to all routes.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing cached images and regenerate from scratch.",
        )

    def handle(self, *args, **options):
        routes     = scan_routes()
        target     = options["route"]
        force      = options["force"]

        if not routes:
            raise CommandError("No routes found in /data folder.")

        if target:
            if target not in routes:
                raise CommandError(
                    f"Route '{target}' not found. Available: {', '.join(routes.keys())}"
                )
            selected = {target: routes[target]}
        else:
            selected = routes

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n  Generating maps for {len(selected)} route(s)  "
            )
        )
        self.stdout.write(f"  Cache directory: {CACHE_DIR}\n")

        total_ok    = 0
        total_fail  = 0
        t_start     = time.time()

        for route_id, info in selected.items():
            self.stdout.write(f"\n{'─' * 56}")
            self.stdout.write(
                self.style.SUCCESS(f"  Route: {route_id}") + f"  ({info['label']})"
            )

            if force:
                deleted = clear_route_cache(route_id)
                if deleted:
                    self.stdout.write(f"  Cleared {deleted} cached image(s).")

            # Load data
            try:
                df_features, df_pp, _ = load_route_data(info["xlsx"])
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  Could not load data: {exc}"))
                continue

            tour = build_tour(df_features, df_pp)

            route_coords = get_alignment_coords(info, df_features)

            total_stops = len(tour)
            self.stdout.write(f"  {total_stops} stops to process...\n")

            ok   = 0
            fail = 0

            for i, stop in enumerate(tour, start=1):
                label = f"{stop['id']:>12}  {stop['label']:<28}  {stop['chainage']:>8.1f} m"

                # Skip if both images already cached and not forcing
                safe_id      = str(stop["id"]).replace("/", "_").replace(" ", "_")
                overview_cached = (CACHE_DIR / f"{route_id}_{safe_id}_overview.png").exists()
                detail_cached   = (CACHE_DIR / f"{route_id}_{safe_id}_detail.png").exists()

                if overview_cached and detail_cached and not force:
                    self.stdout.write(f"  [{i:>3}/{total_stops}]  ✓ cached  {label}")
                    ok += 1
                    continue

                try:
                    maps = get_stop_maps(route_id, stop, route_coords)
                    if maps["overview_url"] and maps["detail_url"]:
                        self.stdout.write(
                            self.style.SUCCESS(f"  [{i:>3}/{total_stops}]  ✓ ok     ") + label
                        )
                        ok += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"  [{i:>3}/{total_stops}]  ⚠ partial") + f"  {label}"
                        )
                        fail += 1
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(f"  [{i:>3}/{total_stops}]  ✗ error  ") + f"{label}  → {exc}"
                    )
                    fail += 1

            self.stdout.write(
                f"\n  Route done — {ok} ok, {fail} failed  "
                f"({ok * 2} images in cache)"
            )
            total_ok   += ok
            total_fail += fail

        elapsed = time.time() - t_start
        self.stdout.write(f"\n{'═' * 56}")
        self.stdout.write(
            self.style.SUCCESS(
                f"  Complete — {total_ok} stops ok, {total_fail} failed  "
                f"({elapsed:.1f}s)\n"
            )
        )
