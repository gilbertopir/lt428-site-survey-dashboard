"""
survey/services/map_renderer.py

Generates static satellite map images for each stop in the route report.
- Overview map: full route line + red circle at the stop location
- Detail map:   zoomed in tight to the stop

Images are cached to media/map_cache/ so they are only generated once per stop.
First load of the report will be slow (tile fetching); all subsequent loads are instant.
"""

from pathlib import Path

from django.conf import settings
from staticmap import CircleMarker, Line, StaticMap

# ── Config ────────────────────────────────────────────────────────────────────
TILE_URL  = (
    "https://server.arcgisonline.com/ArcGIS/rest/services"
    "/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
CACHE_DIR  = settings.MEDIA_ROOT / "map_cache"
MAP_W, MAP_H = 520, 300   # pixel dimensions for both map types

# Marker style
STOP_COLOUR    = "#ff3333"   # red fill
STOP_OUTLINE   = "#ffffff"   # white ring
MARKER_RADIUS  = 9
OUTLINE_RADIUS = 14          # drawn first as background circle

ROUTE_LINE_COLOUR = "#ffffff"
ROUTE_LINE_WIDTH  = 2


# ── Public API ────────────────────────────────────────────────────────────────
def get_stop_maps(route_id: str, stop: dict, route_coords: list[tuple]) -> dict:
    """
    Return {'overview_url': str|None, 'detail_url': str|None} for a stop.

    route_coords — list of (lat, lon) tuples for the full route alignment,
                   used to draw the white route line on the overview map.
    """
    lat = stop.get("lat")
    lon = stop.get("lon")

    if not lat or not lon:
        return {"overview_url": None, "detail_url": None}

    # Sanitise stop id for use in filename (remove slashes, spaces etc.)
    safe_id = str(stop["id"]).replace("/", "_").replace(" ", "_")

    overview_url = _ensure_map(
        cache_name=f"{route_id}_{safe_id}_overview.png",
        render_fn=lambda: _render_overview(lat, lon, route_coords),
    )
    detail_url = _ensure_map(
        cache_name=f"{route_id}_{safe_id}_detail.png",
        render_fn=lambda: _render_detail(lat, lon),
    )

    return {"overview_url": overview_url, "detail_url": detail_url}


def clear_route_cache(route_id: str) -> int:
    """Delete all cached map images for a route. Returns count deleted."""
    if not CACHE_DIR.exists():
        return 0
    deleted = 0
    for f in CACHE_DIR.glob(f"{route_id}_*.png"):
        f.unlink()
        deleted += 1
    return deleted


# ── Internal helpers ──────────────────────────────────────────────────────────
def _ensure_map(cache_name: str, render_fn) -> str | None:
    """Return media URL for cached image, generating it if missing."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name

    if not path.exists():
        try:
            image = render_fn()
            image.save(str(path))
        except Exception as exc:
            print(f"[map_renderer] Failed to generate {cache_name}: {exc}")
            return None

    return f"/media/map_cache/{cache_name}"


def _render_overview(lat: float, lon: float, route_coords: list[tuple]):
    """Full route overview with route line and stop marker."""
    m = StaticMap(MAP_W, MAP_H, url_template=TILE_URL)

    # Route alignment line
    if route_coords and len(route_coords) >= 2:
        # staticmap expects (lon, lat) — swap from our (lat, lon) storage
        line_coords = [(c[1], c[0]) for c in route_coords]
        m.add_line(Line(line_coords, ROUTE_LINE_COLOUR, ROUTE_LINE_WIDTH))

    # Stop marker: white outer ring + red fill
    m.add_marker(CircleMarker((lon, lat), STOP_OUTLINE, OUTLINE_RADIUS))
    m.add_marker(CircleMarker((lon, lat), STOP_COLOUR,  MARKER_RADIUS))

    return m.render()   # auto-fit zoom to show all content


def _render_detail(lat: float, lon: float):
    """Tight zoom on the stop location."""
    m = StaticMap(MAP_W, MAP_H, url_template=TILE_URL)
    m.add_marker(CircleMarker((lon, lat), STOP_OUTLINE, OUTLINE_RADIUS))
    m.add_marker(CircleMarker((lon, lat), STOP_COLOUR,  MARKER_RADIUS))
    return m.render(zoom=18)
