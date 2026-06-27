"""
survey/services/data_loader.py
Adapted from Streamlit data_loader.py for Django.
Route scanning, xlsx loading, DXF parsing, BNG→WGS84 conversion.
"""

import glob
from pathlib import Path

import ezdxf
import pandas as pd
from django.conf import settings
from pyproj import Transformer

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR                 = settings.DATA_DIR
MEDIA_ROOT               = settings.MEDIA_ROOT
PHOTO_DIR_FEATURES       = MEDIA_ROOT / 'photos' / 'features'
PHOTO_DIR_PASSING_PLACES = MEDIA_ROOT / 'photos' / 'passing_places'

# ── Colour maps ───────────────────────────────────────────────────────────────
FEATURE_COLORS = {
    # Access & movement
    'Accesses / driveways':      '#3498db',
    'Junctions':                 '#2980b9',
    'Bus stops / laybys':        '#1abc9c',
    # Drainage
    'Gullies':                   '#00bcd4',
    'Culverts / headwalls':      '#0097a7',
    'Drainage ditches':          '#26c6da',
    'Manholes / chambers':       '#4dd0e1',
    'Ponding / drainage issues': '#006064',
    'Watercourses':              '#00838f',
    # Structures & barriers
    'Fencing':                   '#f39c12',
    'Gates':                     '#e67e22',
    'Bollards':                  '#ff8f00',
    'Existing walls':            '#ff7043',
    'Retaining walls':           '#bf360c',
    'Kerbs / edging':            '#ffb300',
    # Signage & lighting
    'Sign posts':                '#e74c3c',
    'Sign faces':                '#c0392b',
    'Traffic signals':           '#ff5252',
    'Lighting columns':          '#ffd600',
    'Overhead lines / poles':    '#f9a825',
    # Vegetation & earthworks
    'Hedges':                    '#43a047',
    'Trees':                     '#2e7d32',
    'Verge edges':               '#66bb6a',
    'Cuttings':                  '#a5d6a7',
    'Embankments':               '#81c784',
    # Road surface & defects
    'Edge break-up':             '#9c27b0',
    'Pavement defects':          '#7b1fa2',
    'Road markings':             '#ce93d8',
    # Utilities
    'Cabinets / comms boxes':    '#ff6f00',
    'Utility covers':            '#ef6c00',
    'Utility marker posts':      '#e65100',
    'VRS':                       '#d84315',
    # Other
    'Custom / Other':            '#78909c',
}
DEFAULT_COLOR = '#ecf0f1'

CONDITION_COLORS = {
    'GOOD': '#27ae60',
    'FAIR': '#f39c12',
    'POOR': '#e74c3c',
}

# ── Coordinate transform (BNG → WGS84) ───────────────────────────────────────
_transformer = Transformer.from_crs('EPSG:27700', 'EPSG:4326', always_xy=True)


def bng_to_wgs84(easting: float, northing: float) -> tuple:
    lon, lat = _transformer.transform(easting, northing)
    return lat, lon


# ── Route scanning ────────────────────────────────────────────────────────────
def scan_routes() -> dict:
    routes = {}
    for xlsx_path in sorted(glob.glob(str(DATA_DIR / '*.xlsx'))):
        stem     = Path(xlsx_path).stem
        route_id = stem.split('_')[0]
        label    = stem.replace('_', ' ').strip()
        routes[route_id] = {
            'xlsx':  xlsx_path,
            'dxf':   None,
            'label': label,
            'stem':  stem,
        }
    for dxf_path in sorted(glob.glob(str(DATA_DIR / '*.dxf'))):
        route_id = Path(dxf_path).stem.split('_')[0]
        if route_id in routes:
            routes[route_id]['dxf'] = dxf_path
    return routes


# ── Survey data loading ───────────────────────────────────────────────────────
def load_route_data(xlsx_path: str) -> tuple:
    df_features = pd.read_excel(xlsx_path, sheet_name='Features')
    df_pp       = pd.read_excel(xlsx_path, sheet_name='Passing Places')

    # Structures sheet — optional, may be empty or missing
    try:
        df_structures = pd.read_excel(xlsx_path, sheet_name='Structures')
    except Exception:
        df_structures = pd.DataFrame()

    # Summary sheet — optional
    try:
        df_summary = pd.read_excel(xlsx_path, sheet_name='Summary', header=None)
        summary = dict(zip(df_summary.iloc[:, 0], df_summary.iloc[:, 1]))
    except Exception:
        summary = {}

    # Coerce coords
    for col in ['Latitude', 'Longitude']:
        df_features[col] = pd.to_numeric(df_features[col], errors='coerce')
    for col in ['Mid Latitude', 'Mid Longitude']:
        df_pp[col] = pd.to_numeric(df_pp[col], errors='coerce')
    if not df_structures.empty:
        for col in ['Latitude', 'Longitude']:
            if col in df_structures.columns:
                df_structures[col] = pd.to_numeric(df_structures[col], errors='coerce')
        if 'Condition' in df_structures.columns:
            df_structures['Condition'] = df_structures['Condition'].astype(str).str.upper().replace('NAN', 'UNKNOWN').fillna('UNKNOWN')

    # Normalise conditions
    df_features['Condition'] = df_features['Condition'].astype(str).str.upper().replace('NAN', 'UNKNOWN').fillna('UNKNOWN')

    return df_features, df_pp, df_structures, summary


def _fmt_en(val) -> str:
    if val == '':
        return ''
    try:
        return f"{float(val):,.1f}"
    except (ValueError, TypeError):
        return str(val)


# ── Build tour (chainage-ordered merge for report + photo tour) ───────────────
def build_tour(df_features, df_pp, df_structures=None) -> list:
    """
    Merge features and passing places, sort by chainage.
    Returns a list of dicts ready for template rendering.
    Each dict has a consistent set of keys regardless of source type.
    """
    stops = []

    for _, row in df_features.iterrows():
        photo_file = str(row.get('Photo', '') or '').strip()
        photo_urls = _photo_urls('features', photo_file)

        stops.append({
            'type':       'Feature',
            'id':         row['ID'],
            'chainage':   row['Chainage (m)'],
            'label':      row['Feature Type'],
            'condition':  str(row['Condition']),
            'side':       row.get('Side', ''),
            'notes':      str(row.get('Notes', '') or '').strip(),
            'lat':        row.get('Latitude'),
            'lon':        row.get('Longitude'),
            'photo_urls': photo_urls,
            'color':     FEATURE_COLORS.get(row['Feature Type'], DEFAULT_COLOR),
            'cond_color': CONDITION_COLORS.get(str(row['Condition']).upper(), DEFAULT_COLOR),
            'easting':  row.get('Easting', ''),
            'northing': row.get('Northing', ''),
            'specs': [
                ('Easting',  _fmt_en(row.get('Easting', ''))),
                ('Northing', _fmt_en(row.get('Northing', ''))),
                ('Offset from Edge', f"{row.get('Offset from Edge (m)', '')} m"),
                ('GPS Accuracy',     f"± {row.get('GPS Accuracy (m)', '')} m"),
                ('Captured By',      str(row.get('Captured By', ''))),
                ('Captured At',      str(row.get('Captured At', ''))[:16]),
            ],
        })

    for _, row in df_pp.iterrows():
        photo_file = str(row.get('Photo', '') or '').strip()
        photo_urls = _photo_urls('passing_places', photo_file)

        stops.append({
            'type':       'Passing Place',
            'id':         row['PP ID'],
            'chainage':   row['Mid Chainage (m)'],
            'label':      'Passing Place',
            'condition':  str(row.get('Status', '')),
            'side':       row.get('Side', ''),
            'notes':      str(row.get('Notes', '') or '').strip(),
            'lat':        row.get('Mid Latitude'),
            'lon':        row.get('Mid Longitude'),
            'photo_urls': photo_urls,
            'color':     '#2ecc71',
            'cond_color': '#2ecc71',
            'easting':  row.get('Mid Easting', ''),
            'northing': row.get('Mid Northing', ''),
            'specs': [
                ('Easting',  _fmt_en(row.get('Mid Easting', ''))),
                ('Northing', _fmt_en(row.get('Mid Northing', ''))),
                ('Down Road Width',         f"{row.get('Down Chainage Road Width (m)', '')} m"),
                ('Down Taper Length',       f"{row.get('Down Chainage Taper Length (m)', '')} m"),
                ('Usable Length',           f"{row.get('Usable Length (m)', '')} m"),
                ('Vehicle Clearance Width', f"{row.get('Width (Vehicle Clearance) (m)', '')} m"),
                ('Total Length',            f"{row.get('Total Length (m)', '')} m"),
                ('Up Road Width',           f"{row.get('Up Chainage Road Width (m)', '')} m"),
                ('Up Taper Length',         f"{row.get('Up Chainage Taper Length (m)', '')} m"),
                ('GPS Accuracy', f"± {row.get('GPS Accuracy (m)', '')} m"),
                ('Captured By',  str(row.get('Captured By', ''))),
                ('Captured At',  str(row.get('Captured At', ''))[:16]),
            ],
        })

    # Structures
    if df_structures is not None and not (hasattr(df_structures, 'empty') and df_structures.empty):
        for _, row in df_structures.iterrows():
            photo_file = str(row.get('Photo', '') or '').strip()
            photo_urls = _photo_urls('structures', photo_file)
            stops.append({
                'type':      'Structure',
                'id':        str(row.get('ID', '')),
                'chainage':  row.get('Chainage (m)', 0),
                'label':     str(row.get('Structure Name', '') or row.get('Feature Type', '')),
                'condition': str(row.get('Condition', '') or ''),
                'side':      str(row.get('Side', '') or ''),
                'notes':     str(row.get('Notes', '') or '').strip(),
                'lat':       row.get('Latitude'),
                'lon':       row.get('Longitude'),
                'photo_urls': photo_urls,
                'color':     '#e74c3c',
                'cond_color': CONDITION_COLORS.get(str(row.get('Condition', '')).upper(), '#607d8b'),
                'specs': [
                    ('Structure Name',      str(row.get('Structure Name', '') or '')),
                    ('Feature Type',        str(row.get('Feature Type', '') or '')),
                    ('Easting',             _fmt_en(row.get('Easting', ''))),
                    ('Northing',            _fmt_en(row.get('Northing', ''))),
                    ('Span',                f"{row.get('Span (mm)', '')} mm"),
                    ('Rise',                f"{row.get('Rise (mm)', '')} mm"),
                    ('Vehicle Clearance',   f"{row.get('Vehicle Clearance (mm)', '')} mm"),
                    ('Parapet Height',      f"{row.get('Parapet Height (mm)', '')} mm"),
                    ('Parapet Thickness',   f"{row.get('Parapet Thickness (mm)', '')} mm"),
                    ('Footpath Width',      f"{row.get('Footpath Width (mm)', '')} mm"),
                    ('Type of Stone',       str(row.get('Type of Stone', '') or '')),
                    ('Recommended Action',  str(row.get('Recommended Action', '') or '')),
                    ('GPS Accuracy',        f"± {row.get('GPS Accuracy (m)', '')} m"),
                    ('Captured By',         str(row.get('Captured By', '') or '')),
                    ('Captured At',         str(row.get('Captured At', '') or '')[:16]),
                ],
            })

    stops.sort(key=lambda s: float(s['chainage']) if s['chainage'] else 0)
    return stops


# ── Photo URL helper ──────────────────────────────────────────────────────────
def _photo_urls(subfolder: str, raw_field: str) -> list:
    """
    The Photo field may contain one filename or several comma-separated ones.
    Returns a list of valid media URLs for files that exist on disk.
    Django serves /media/ in dev via config/urls.py static() helper.
    """
    if not raw_field:
        return []
    urls = []
    for filename in raw_field.split(','):
        filename = filename.strip()
        if not filename:
            continue
        rel_path = Path('photos') / subfolder / filename
        abs_path = MEDIA_ROOT / rel_path
        if abs_path.exists():
            urls.append(f'/media/{rel_path.as_posix()}')
    return urls


# ── DXF parsing ───────────────────────────────────────────────────────────────
def parse_dxf_alignment(dxf_path: str, layer_name: str = None) -> list:
    doc  = ezdxf.readfile(dxf_path)
    msp  = doc.modelspace()
    lines = []

    def layer_ok(e):
        return layer_name is None or e.dxf.layer == layer_name

    for e in msp.query('LWPOLYLINE'):
        if not layer_ok(e):
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if pts:
            lines.append([bng_to_wgs84(x, y) for x, y in pts])

    if not lines:
        for e in msp.query('POLYLINE'):
            if not layer_ok(e):
                continue
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if pts:
                lines.append([bng_to_wgs84(x, y) for x, y in pts])

    if not lines:
        segments = []
        for e in msp.query('LINE'):
            if not layer_ok(e):
                continue
            segments.append((
                (e.dxf.start.x, e.dxf.start.y),
                (e.dxf.end.x,   e.dxf.end.y),
            ))
        if segments:
            ordered = sorted(segments, key=lambda s: s[0][0])
            pts = [ordered[0][0]] + [s[1] for s in ordered]
            lines.append([bng_to_wgs84(x, y) for x, y in pts])

    return sorted(lines, key=len, reverse=True)


def feature_color(feature_type: str) -> str:
    return FEATURE_COLORS.get(feature_type, DEFAULT_COLOR)


def condition_color(condition: str) -> str:
    return CONDITION_COLORS.get(str(condition).upper(), DEFAULT_COLOR)


# ── DXF route length ─────────────────────────────────────────────────────────
def get_route_length_m(info: dict, df_features) -> float | None:
    """
    Returns total route length in metres.
    Uses DXF polyline length if available (accurate full-route length),
    falls back to chainage range from survey data.
    """
    if info.get('dxf'):
        try:
            import math
            doc  = ezdxf.readfile(info['dxf'])
            msp  = doc.modelspace()
            # Try LWPOLYLINE first
            for e in msp.query('LWPOLYLINE'):
                pts = list(e.get_points())
                if len(pts) > 1:
                    length = sum(
                        math.sqrt((pts[i+1][0]-pts[i][0])**2 + (pts[i+1][1]-pts[i][1])**2)
                        for i in range(len(pts)-1)
                    )
                    return round(length)
            # Fall back to POLYLINE
            for e in msp.query('POLYLINE'):
                verts = list(e.vertices)
                if len(verts) > 1:
                    length = sum(
                        math.sqrt(
                            (verts[i+1].dxf.location.x - verts[i].dxf.location.x)**2 +
                            (verts[i+1].dxf.location.y - verts[i].dxf.location.y)**2
                        )
                        for i in range(len(verts)-1)
                    )
                    return round(length)
        except Exception as exc:
            print(f'[data_loader] DXF length failed: {exc}')

    # Fallback — chainage range from survey points
    try:
        if df_features is not None and not df_features.empty:
            ch_min = float(df_features['Chainage (m)'].min())
            ch_max = float(df_features['Chainage (m)'].max())
            if not (ch_min != ch_min or ch_max != ch_max):  # NaN check
                return round(ch_max - ch_min)
    except Exception:
        pass
    return None


# ── Best-available alignment coords ──────────────────────────────────────────
def get_alignment_coords(info: dict, df_features) -> list:
    """
    Returns list of (lat, lon) tuples for the route alignment.
    Uses DXF centreline if available, falls back to GPS survey points.
    """
    if info.get('dxf'):
        try:
            lines = parse_dxf_alignment(info['dxf'])
            if lines and lines[0]:
                return lines[0]  # longest line first
        except Exception as exc:
            print(f"[data_loader] DXF parse failed, using GPS fallback: {exc}")

    # Fallback — GPS survey points sorted by chainage
    return (
        df_features.dropna(subset=['Latitude', 'Longitude'])
        .sort_values('Chainage (m)')[['Latitude', 'Longitude']]
        .values.tolist()
    )
