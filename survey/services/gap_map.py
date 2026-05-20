"""
survey/services/gap_map.py

Generates a static satellite map showing survey coverage:
  - Full DXF route in white
  - Surveyed section in green
  - Flagged gaps in red
  - First/last capture point markers

Cached to media/map_cache/ like aerial maps.
"""

import math
from pathlib import Path

from django.conf import settings
from staticmap import CircleMarker, Line, StaticMap

TILE_URL  = (
    "https://server.arcgisonline.com/ArcGIS/rest/services"
    "/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
CACHE_DIR = settings.MEDIA_ROOT / "map_cache"
MAP_W, MAP_H = 900, 400


def get_coverage_map(route_id: str, dxf_coords: list, survey_points: list,
                     flagged_gaps: list, passing_places: list = None) -> str | None:
    """
    Generate and cache a coverage map image.

    dxf_coords      — list of (lat, lon) for full DXF route
    passing_places  — list of dicts with lat, lon for PP markers
    survey_points — list of dicts with 'lat', 'lon', 'chainage' sorted by chainage
    flagged_gaps  — list of gap dicts with from/to lat/lon

    Returns media URL string or None on failure.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = f"{route_id}_coverage_map.png"
    cache_path = CACHE_DIR / cache_name

    try:
        m = StaticMap(MAP_W, MAP_H, url_template=TILE_URL)

        # ── Full DXF route — white semi-transparent ────────────────
        if dxf_coords and len(dxf_coords) >= 2:
            line_coords = [(c[1], c[0]) for c in dxf_coords]  # (lon, lat)
            m.add_line(Line(line_coords, "#ffffff", 2))

        # ── Surveyed section — green ───────────────────────────────
        valid_pts = [p for p in survey_points if p.get('lat') and p.get('lon')]
        if valid_pts and len(valid_pts) >= 2:
            surveyed_coords = [(p['lon'], p['lat']) for p in valid_pts]
            m.add_line(Line(surveyed_coords, "#27ae60", 3))

        # ── Flagged gaps — red ─────────────────────────────────────
        for gap in flagged_gaps:
            if gap.get('from_lat') and gap.get('to_lat'):
                gap_coords = [
                    (gap['from_lon'], gap['from_lat']),
                    (gap['to_lon'],   gap['to_lat']),
                ]
                m.add_line(Line(gap_coords, "#e74c3c", 4))

        # ── First/last survey point markers ────────────────────────
        if valid_pts:
            first = valid_pts[0]
            last  = valid_pts[-1]
            m.add_marker(CircleMarker((first['lon'], first['lat']), "#27ae60", 10))
            m.add_marker(CircleMarker((last['lon'],  last['lat']),  "#f39c12", 10))

        # ── Passing place markers — yellow with black outline ───────
        for pp in (passing_places or []):
            if pp.get('lat') and pp.get('lon'):
                m.add_marker(CircleMarker((pp['lon'], pp['lat']), "#000000", 11))
                m.add_marker(CircleMarker((pp['lon'], pp['lat']), "#f1c40f", 8))

        image = m.render()
        image.save(str(cache_path))
        return f"/media/map_cache/{cache_name}"

    except Exception as exc:
        print(f"[gap_map] Failed for {route_id}: {exc}")
        return None


def clear_coverage_map(route_id: str):
    path = CACHE_DIR / f"{route_id}_coverage_map.png"
    if path.exists():
        path.unlink()
