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


# ── OSM Report Overview Map ───────────────────────────────────────────────────
OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def _haversine_m(lat1, lon1, lat2, lon2):
    """Distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _map_zoom(route_length_m: float) -> int:
    """Pick a fixed zoom level based on route length for consistent map scale."""
    if   route_length_m <  200: return 16
    elif route_length_m <  500: return 15
    elif route_length_m < 1500: return 14
    elif route_length_m < 4000: return 13
    elif route_length_m < 8000: return 12
    else:                       return 11


def _chainage_interval(route_length_m: float) -> int:
    """Auto-select chainage marker interval based on route length."""
    if   route_length_m <   50: return 10
    elif route_length_m <  100: return 20
    elif route_length_m <  250: return 50
    elif route_length_m <  500: return 100
    elif route_length_m < 1000: return 200
    else:                       return 500


def _interpolate_points(coords, interval_m):
    """
    Walk a lat/lon polyline and return points at every interval_m metres.
    coords — list of (lat, lon)
    Returns list of (lat, lon) at each interval.
    """
    markers = []
    if len(coords) < 2:
        return markers

    cumulative = 0.0
    next_target = interval_m
    markers.append(coords[0])   # always include start (CH0)

    for i in range(1, len(coords)):
        prev = coords[i-1]
        curr = coords[i]
        seg_len = _haversine_m(prev[0], prev[1], curr[0], curr[1])

        while cumulative + seg_len >= next_target:
            # Interpolate position along this segment
            frac = (next_target - cumulative) / seg_len if seg_len > 0 else 0
            lat  = prev[0] + frac * (curr[0] - prev[0])
            lon  = prev[1] + frac * (curr[1] - prev[1])
            markers.append((lat, lon))
            next_target += interval_m

        cumulative += seg_len

    return markers


def get_report_overview_map(route_id: str, dxf_coords: list,
                             survey_points: list = None) -> tuple:
    """
    Generate a clean OpenStreetMap overview showing the full route.
    Returns (image_url, interval_m) tuple.

    dxf_coords    — list of (lat, lon) for full DXF route
    survey_points — optional list of dicts with lat/lon (green line overlay)
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = f"{route_id}_report_overview.png"
    cache_path = CACHE_DIR / cache_name

    # Calculate route length and interval
    route_length_m = 0
    if dxf_coords and len(dxf_coords) >= 2:
        for i in range(1, len(dxf_coords)):
            route_length_m += _haversine_m(
                dxf_coords[i-1][0], dxf_coords[i-1][1],
                dxf_coords[i][0],   dxf_coords[i][1]
            )
    interval_m = _chainage_interval(route_length_m) if route_length_m > 0 else 500
    zoom       = _map_zoom(route_length_m) if route_length_m > 0 else 13

    if cache_path.exists():
        return f"/media/map_cache/{cache_name}", interval_m

    try:
        m = StaticMap(900, 420, url_template=OSM_TILE_URL)

        # ── Full DXF route — dark navy line ────────────────────────
        if dxf_coords and len(dxf_coords) >= 2:
            line_coords = [(c[1], c[0]) for c in dxf_coords]
            m.add_line(Line(line_coords, "#051b63", 4))

        # ── Surveyed section overlay — green ───────────────────────
        if survey_points and len(survey_points) >= 2:
            surveyed = [(p["lon"], p["lat"]) for p in survey_points
                        if p.get("lat") and p.get("lon")]
            if len(surveyed) >= 2:
                m.add_line(Line(surveyed, "#27ae60", 2))

        # ── Chainage interval markers — yellow, drawn before start/end ──
        if dxf_coords and len(dxf_coords) >= 2:
            ch_points = _interpolate_points(dxf_coords, interval_m)
            for pt in ch_points[1:]:   # skip index 0 (route start)
                m.add_marker(CircleMarker((pt[1], pt[0]), "#000000", 8))
                m.add_marker(CircleMarker((pt[1], pt[0]), "#f1c40f", 6))

        # ── Start and end markers — drawn last, appear on top ──────
        if dxf_coords and len(dxf_coords) >= 2:
            start = dxf_coords[0]
            end   = dxf_coords[-1]
            m.add_marker(CircleMarker((start[1], start[0]), "#000000", 16))
            m.add_marker(CircleMarker((start[1], start[0]), "#051b63", 12))
            m.add_marker(CircleMarker((end[1],   end[0]),   "#000000", 16))
            m.add_marker(CircleMarker((end[1],   end[0]),   "#C41230", 12))

        image = m.render(zoom=zoom)
        image.save(str(cache_path))
        return f"/media/map_cache/{cache_name}", interval_m

    except Exception as exc:
        print(f"[gap_map] Report overview failed for {route_id}: {exc}")
        return None, interval_m


def clear_report_overview_map(route_id: str):
    path = CACHE_DIR / f"{route_id}_report_overview.png"
    if path.exists():
        path.unlink()
