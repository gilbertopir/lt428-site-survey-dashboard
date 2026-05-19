"""
survey/views.py
"""
from django.shortcuts import render, redirect
from django.http import Http404
from .services.data_loader import scan_routes, load_route_data, build_tour, get_alignment_coords


def overview(request):
    routes = scan_routes()
    route_cards = []

    for route_id, info in routes.items():
        try:
            df_features, df_pp, summary = load_route_data(info["xlsx"])
            valid  = df_features.dropna(subset=["Latitude", "Longitude"])
            coords = get_alignment_coords(info, df_features)
            route_cards.append({
                "route_id":   route_id,
                "info":       info,
                "n_features": len(df_features),
                "n_pp":       len(df_pp),
                "n_good":     int((df_features["Condition"] == "GOOD").sum()),
                "n_fair":     int((df_features["Condition"] == "FAIR").sum()),
                "n_poor":     int((df_features["Condition"] == "POOR").sum()),
                "ch_min":     float(df_features["Chainage (m)"].min()),
                "ch_max":     float(df_features["Chainage (m)"].max()),
                "has_dxf":    bool(info["dxf"]),
                "center_lat": float(valid["Latitude"].mean()) if not valid.empty else None,
                "center_lon": float(valid["Longitude"].mean()) if not valid.empty else None,
                "coords":     coords,
            })
        except Exception as exc:
            route_cards.append({"route_id": route_id, "info": info, "error": str(exc)})

    import json

    all_lats = [c["center_lat"] for c in route_cards if c.get("center_lat")]
    all_lons = [c["center_lon"] for c in route_cards if c.get("center_lon")]

    # Build per-route bounds and JSON data for Leaflet map
    map_routes = []
    for card in route_cards:
        if card.get("error") or not card.get("coords"):
            continue
        lats = [c[0] for c in card["coords"]]
        lons = [c[1] for c in card["coords"]]
        bounds = {
            "lat_min": min(lats) - 0.005,
            "lat_max": max(lats) + 0.005,
            "lon_min": min(lons) - 0.005,
            "lon_max": max(lons) + 0.005,
        }
        card["bounds"] = bounds
        map_routes.append({
            "route_id":   card["route_id"],
            "label":      card["info"]["label"],
            "coords":     card["coords"],
            "center":     [card["center_lat"], card["center_lon"]],
            "bounds":     bounds,
            "n_features": card["n_features"],
            "n_pp":       card["n_pp"],
            "n_good":     card["n_good"],
            "n_fair":     card["n_fair"],
            "n_poor":     card["n_poor"],
        })

    all_bounds = None
    if all_lats:
        all_bounds = {
            "lat_min": min(all_lats) - 0.01,
            "lat_max": max(all_lats) + 0.01,
            "lon_min": min(all_lons) - 0.01,
            "lon_max": max(all_lons) + 0.01,
        }

    first_route = list(routes.keys())[0] if routes else None
    return render(request, "survey/overview.html", {
        "routes":      routes,
        "route_cards": route_cards,
        "map_routes":  json.dumps(map_routes),
        "all_bounds":  json.dumps(all_bounds) if all_bounds else "null",
        "first_route": first_route,
    })


def route_detail(request, route_id):
    import json
    import math

    routes = scan_routes()
    if route_id not in routes:
        raise Http404(f"Route {route_id} not found")

    info     = routes[route_id]
    df_features, df_pp, summary = load_route_data(info["xlsx"])

    def safe(val):
        """Convert numpy/nan values to JSON-safe Python types."""
        if val is None:
            return ""
        try:
            if math.isnan(float(val)):
                return ""
        except (TypeError, ValueError):
            pass
        return val

    # Features as JSON for Leaflet markers + inspect panel
    features_json = []
    for _, row in df_features.iterrows():
        if not (safe(row.get("Latitude")) and safe(row.get("Longitude"))):
            continue
        features_json.append({
            "id":         str(row["ID"]),
            "type":       str(row.get("Feature Type", "")),
            "condition":  str(row.get("Condition", "")),
            "side":       str(row.get("Side", "")),
            "chainage":   safe(row.get("Chainage (m)")),
            "offset":     safe(row.get("Offset from Edge (m)")),
            "easting":    safe(row.get("Easting", "")),
            "northing":   safe(row.get("Northing", "")),
            "gps_acc":    safe(row.get("GPS Accuracy (m)")),
            "notes":      str(row.get("Notes", "") or ""),
            "captured_by": str(row.get("Captured By", "") or ""),
            "captured_at": str(row.get("Captured At", "") or "")[:16],
            "lat":        float(row["Latitude"]),
            "lon":        float(row["Longitude"]),
            "kind":       "feature",
        })

    # Passing places as JSON
    pp_json = []
    for _, row in df_pp.iterrows():
        if not (safe(row.get("Mid Latitude")) and safe(row.get("Mid Longitude"))):
            continue
        pp_json.append({
            "id":         str(row["PP ID"]),
            "type":       "Passing Place",
            "condition":  str(row.get("Status", "")),
            "side":       str(row.get("Side", "")),
            "chainage":   safe(row.get("Mid Chainage (m)")),
            "width":      safe(row.get("Width (m)")),
            "length":     safe(row.get("Length (m)")),
            "easting":    safe(row.get("Mid Easting", "")),
            "northing":   safe(row.get("Mid Northing", "")),
            "gps_acc":    safe(row.get("GPS Accuracy (m)")),
            "notes":      str(row.get("Notes", "") or ""),
            "captured_by": str(row.get("Captured By", "") or ""),
            "captured_at": str(row.get("Captured At", "") or "")[:16],
            "lat":        float(row["Mid Latitude"]),
            "lon":        float(row["Mid Longitude"]),
            "kind":       "pp",
        })

    # Route alignment — DXF if available, GPS fallback
    route_coords = get_alignment_coords(info, df_features)

    # Sort both tables by chainage
    df_features  = df_features.sort_values("Chainage (m)").reset_index(drop=True)
    df_pp        = df_pp.sort_values("Mid Chainage (m)").reset_index(drop=True)

    context = {
        "routes":        routes,
        "first_route":   list(routes.keys())[0] if routes else None,
        "route_id":      route_id,
        "info":          info,
        "features":      df_features.to_dict("records"),
        "passing_places": df_pp.to_dict("records"),
        "features_json": json.dumps(features_json),
        "pp_json":       json.dumps(pp_json),
        "route_coords":  json.dumps(route_coords),
        "n_features":    len(df_features),
        "n_pp":          len(df_pp),
        "n_good":        int((df_features["Condition"] == "GOOD").sum()),
        "n_fair":        int((df_features["Condition"] == "FAIR").sum()),
        "n_poor":        int((df_features["Condition"] == "POOR").sum()),
    }
    return render(request, "survey/route_detail.html", context)


def route_report(request, route_id):
    from .services.map_renderer import CACHE_DIR

    routes = scan_routes()
    if route_id not in routes:
        raise Http404(f"Route {route_id} not found")

    info = routes[route_id]
    df_features, df_pp, summary = load_route_data(info['xlsx'])
    tour = build_tour(df_features, df_pp)

    n_good = int((df_features['Condition'] == 'GOOD').sum())
    n_fair = int((df_features['Condition'] == 'FAIR').sum())
    n_poor = int((df_features['Condition'] == 'POOR').sum())

    # Route alignment — DXF if available, GPS fallback
    route_coords = get_alignment_coords(info, df_features)

    # Attach cached map URLs — no generation here, run: python manage.py generate_maps
    for stop in tour:
        safe_id  = str(stop['id']).replace('/', '_').replace(' ', '_')
        overview = CACHE_DIR / f"{route_id}_{safe_id}_overview.png"
        detail   = CACHE_DIR / f"{route_id}_{safe_id}_detail.png"
        stop['overview_map_url'] = f"/media/map_cache/{route_id}_{safe_id}_overview.png" if overview.exists() else None
        stop['detail_map_url']   = f"/media/map_cache/{route_id}_{safe_id}_detail.png"   if detail.exists()   else None

    maps_ready = any(s['overview_map_url'] for s in tour)

    context = {
        'routes':     routes,
        'first_route': list(routes.keys())[0] if routes else None,
        'route_id':   route_id,
        'info':       info,
        'tour':       tour,
        'n_features': len(df_features),
        'n_pp':       len(df_pp),
        'n_good':     n_good,
        'n_fair':     n_fair,
        'n_poor':     n_poor,
        'ch_min':     tour[0]['chainage'] if tour else 0,
        'ch_max':     tour[-1]['chainage'] if tour else 0,
        'maps_ready': maps_ready,
    }
    return render(request, 'survey/report.html', context)


def route_summary(request, route_id):
    routes = scan_routes()
    if route_id not in routes:
        raise Http404(f"Route {route_id} not found")

    info = routes[route_id]
    df_features, df_pp, summary = load_route_data(info['xlsx'])

    context = {
        'routes':     routes,
        'route_id':   route_id,
        'info':       info,
        'summary':    summary,
        'n_features': len(df_features),
        'n_pp':       len(df_pp),
    }
    return render(request, 'survey/summary.html', context)

def photo_library(request):
    import json
    import io
    import zipfile
    from django.http import HttpResponse
    from .services.data_loader import feature_color

    routes = scan_routes()
    if not routes:
        return render(request, 'survey/photo_library.html', {'routes': routes})

    # Route selection
    route_id = request.GET.get('route') or request.POST.get('route') or list(routes.keys())[0]
    if route_id not in routes:
        route_id = list(routes.keys())[0]

    info = routes[route_id]
    df_features, df_pp, summary = load_route_data(info['xlsx'])

    # ── Filters ───────────────────────────────────────────────
    q_id      = request.GET.get('q_id', '').strip().lower()
    q_type    = request.GET.get('q_type', '')
    ch_min    = request.GET.get('ch_min', '')
    ch_max    = request.GET.get('ch_max', '')
    photos_only = request.GET.get('photos_only', '') == '1'

    def apply_filters(df, id_col, chainage_col, type_col=None):
        if q_id:
            df = df[df[id_col].astype(str).str.lower().str.contains(q_id)]
        if q_type and type_col:
            df = df[df[type_col] == q_type]
        if ch_min:
            try: df = df[df[chainage_col] >= float(ch_min)]
            except: pass
        if ch_max:
            try: df = df[df[chainage_col] <= float(ch_max)]
            except: pass
        return df

    df_f  = apply_filters(df_features.copy(), 'ID', 'Chainage (m)', 'Feature Type')
    df_pp = apply_filters(df_pp.copy(), 'PP ID', 'Mid Chainage (m)')

    # ── Build photo items ─────────────────────────────────────
    import math
    def safe_str(val):
        if val is None: return ''
        try:
            if math.isnan(float(val)): return ''
        except: pass
        return str(val).strip()

    def make_new_name(route_id, item_id, feature_type, condition, chainage, original):
        ext = original.rsplit('.', 1)[-1] if '.' in original else 'jpg'
        ch  = f"CH{float(chainage):.0f}m" if chainage else ''
        parts = [p for p in [route_id, item_id, feature_type, condition, ch] if p]
        return '_'.join(parts).replace(' ', '_').replace('/', '_') + '.' + ext

    items = []
    for _, row in df_f.iterrows():
        photos = [p.strip() for p in str(row.get('Photo', '') or '').split(',') if p.strip()]
        if photos_only and not photos:
            continue
        for i, photo in enumerate(photos):
            from pathlib import Path
            from django.conf import settings
            path = settings.MEDIA_ROOT / 'photos' / 'features' / photo
            new_name = make_new_name(
                route_id, safe_str(row['ID']),
                safe_str(row.get('Feature Type', '')),
                safe_str(row.get('Condition', '')),
                row.get('Chainage (m)', ''), photo
            )
            items.append({
                'id':           safe_str(row['ID']),
                'kind':         'feature',
                'type':         safe_str(row.get('Feature Type', '')),
                'condition':    safe_str(row.get('Condition', '')),
                'chainage':     row.get('Chainage (m)', ''),
                'side':         safe_str(row.get('Side', '')),
                'photo':        photo,
                'new_name':     new_name,
                'has_photo':    path.exists(),
                'photo_url':    f'/media/photos/features/{photo}' if path.exists() else None,
                'captured_at':  safe_str(row.get('Captured At', ''))[:10],
            })


    for _, row in df_pp.iterrows():
        photos = [p.strip() for p in str(row.get('Photo', '') or '').split(',') if p.strip()]
        if photos_only and not photos:
            continue
        for i, photo in enumerate(photos):
            from pathlib import Path
            from django.conf import settings
            path = settings.MEDIA_ROOT / 'photos' / 'passing_places' / photo
            new_name = make_new_name(
                route_id, safe_str(row['PP ID']),
                'PassingPlace',
                safe_str(row.get('Status', '')),
                row.get('Mid Chainage (m)', ''), photo
            )
            items.append({
                'id':           safe_str(row['PP ID']),
                'kind':         'pp',
                'type':         'Passing Place',
                'condition':    safe_str(row.get('Status', '')),
                'chainage':     row.get('Mid Chainage (m)', ''),
                'side':         safe_str(row.get('Side', '')),
                'photo':        photo,
                'new_name':     new_name,
                'has_photo':    path.exists(),
                'photo_url':    f'/media/photos/passing_places/{photo}' if path.exists() else None,
                'captured_at':  safe_str(row.get('Captured At', ''))[:10],
            })


    # Keep only items with photos and sort by chainage
    items = [i for i in items if i['has_photo']]
    items.sort(key=lambda x: float(x['chainage']) if x['chainage'] else 0)

    # ── Download zip of selected photos ──────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'download_photos':
        selected = request.POST.getlist('selected_photos')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in items:
                if item['photo'] in selected and item['has_photo']:
                    subfolder = 'passing_places' if item['kind'] == 'pp' else 'features'
                    src = settings.MEDIA_ROOT / 'photos' / subfolder / item['photo']
                    zf.write(src, item['new_name'])
        buf.seek(0)
        resp = HttpResponse(buf, content_type='application/zip')
        resp['Content-Disposition'] = f'attachment; filename="{route_id}_photos.zip"'
        return resp

    # ── Download Excel ────────────────────────────────────────
    if request.GET.get('action') == 'download_excel':
        import openpyxl
        from openpyxl.styles import PatternFill, Font
        wb = openpyxl.Workbook()

        # Features sheet — drop Photo column
        df_features_dl = df_features.drop(columns=['Photo'], errors='ignore')
        df_pp_dl       = df_pp.drop(columns=['Photo'], errors='ignore')

        ws1 = wb.active
        ws1.title = 'Features'
        headers = list(df_features_dl.columns)
        ws1.append(headers)
        for cell in ws1[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='051b63')
            cell.font = Font(bold=True, color='FFFFFF')
        for _, row in df_features_dl.iterrows():
            ws1.append([str(v) if v is not None else '' for v in row])

        # Passing Places sheet — drop Photo column
        ws2 = wb.create_sheet('Passing Places')
        headers2 = list(df_pp_dl.columns)
        ws2.append(headers2)
        for cell in ws2[1]:
            cell.fill = PatternFill('solid', fgColor='051b63')
            cell.font = Font(bold=True, color='FFFFFF')
        for _, row in df_pp_dl.iterrows():
            ws2.append([str(v) if v is not None else '' for v in row])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = HttpResponse(buf, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{route_id}_survey_data.xlsx"'
        return resp

    feature_types = sorted(df_features['Feature Type'].dropna().unique())
    ch_min_val = float(df_features['Chainage (m)'].min())
    ch_max_val = float(df_features['Chainage (m)'].max())

    context = {
        'routes':        routes,
        'first_route':   list(routes.keys())[0] if routes else None,
        'route_id':      route_id,
        'info':          info,
        'items':         items,
        'feature_types': feature_types,
        'ch_min_val':    ch_min_val,
        'ch_max_val':    ch_max_val,
        'q_id':          q_id,
        'q_type':        q_type,
        'ch_min':        ch_min,
        'ch_max':        ch_max,
        'photos_only':   photos_only,
        'total':         len(items),
        'with_photos':   sum(1 for i in items if i['has_photo']),
    }
    return render(request, 'survey/photo_library.html', context)
