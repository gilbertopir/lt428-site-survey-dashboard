"""
survey/admin.py

Custom Django admin for the Site Survey Dashboard.
Superusers can generate (or regenerate) static satellite map images
for any route directly from the browser — no terminal access needed.
"""

import time

from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html

from .models import MapGenerationLog
from .services.data_loader import scan_routes, load_route_data, build_tour, get_alignment_coords
from .services.map_renderer import get_stop_maps, clear_route_cache, CACHE_DIR


# ── Admin site customisation ──────────────────────────────────────────────────
admin.site.site_header  = "LT428 — Site Survey Admin"
admin.site.site_title   = "Survey Admin"
admin.site.index_title  = "Survey Administration"


# ── MapGenerationLog admin ────────────────────────────────────────────────────
@admin.register(MapGenerationLog)
class MapGenerationLogAdmin(admin.ModelAdmin):
    change_list_template = "admin/survey/mapgenerationlog/change_list.html"

    list_display  = (
        "route_id", "status_badge", "success_count", "fail_count",
        "total_stops", "duration_display", "generated_at", "generate_button",
    )
    readonly_fields = (
        "route_id", "generated_at", "total_stops",
        "success_count", "fail_count", "duration_secs",
    )
    ordering = ["route_id"]

    # ── Remove default add/delete — generation is via custom view ─────────────
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # ── Extra URL: generation view ────────────────────────────────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "generate/",
                self.admin_site.admin_view(self.generate_overview_view),
                name="survey_generate_overview",
            ),
            path(
                "generate/<str:route_id>/",
                self.admin_site.admin_view(self.generate_route_view),
                name="survey_generate_route",
            ),
            path(
                "upload/",
                self.admin_site.admin_view(self.upload_route_view),
                name="survey_upload_route",
            ),
            path(
                "delete-route/",
                self.admin_site.admin_view(self.delete_route_view),
                name="survey_delete_route",
            ),
            path(
                "delete-photos/",
                self.admin_site.admin_view(self.delete_photos_view),
                name="survey_delete_photos",
            ),
        ]
        return custom + urls

    # ── Upload route data ────────────────────────────────────────────────────────
    def upload_route_view(self, request):
        import os
        import zipfile
        from django.conf import settings
        DATA_DIR   = settings.DATA_DIR
        MEDIA_ROOT = settings.MEDIA_ROOT

        IMAGE_EXTS = ('.jpg', '.jpeg', '.png')

        def save_photos(files, dest_dir):
            """Save a list of uploaded files (images or zips) to dest_dir."""
            dest_dir.mkdir(parents=True, exist_ok=True)
            count = 0
            for f in files:
                name = f.name.lower()
                if name.endswith('.zip'):
                    # Extract images from zip
                    with zipfile.ZipFile(f, 'r') as z:
                        for member in z.namelist():
                            filename = os.path.basename(member)
                            if not filename or filename.startswith('.'):
                                continue
                            if filename.lower().endswith(IMAGE_EXTS):
                                with z.open(member) as src, open(dest_dir / filename, 'wb') as dst:
                                    dst.write(src.read())
                                count += 1
                elif name.endswith(IMAGE_EXTS):
                    # Save image directly
                    filename = os.path.basename(f.name)
                    with open(dest_dir / filename, 'wb') as dst:
                        for chunk in f.chunks():
                            dst.write(chunk)
                    count += 1
            return count

        success_msgs = []
        error_msgs   = []

        if request.method == 'POST':
            # xlsx
            xlsx = request.FILES.get('xlsx_file')
            if xlsx:
                dest = DATA_DIR / xlsx.name
                with open(dest, 'wb') as f:
                    for chunk in xlsx.chunks():
                        f.write(chunk)
                success_msgs.append(f'✅ Survey data saved: {xlsx.name}')

            # dxf
            dxf = request.FILES.get('dxf_file')
            if dxf:
                dest = DATA_DIR / dxf.name
                with open(dest, 'wb') as f:
                    for chunk in dxf.chunks():
                        f.write(chunk)
                success_msgs.append(f'✅ DXF alignment saved: {dxf.name}')

            # feature photos — multiple files or zip
            feat_files = request.FILES.getlist('feature_photos')
            if feat_files:
                try:
                    count = save_photos(feat_files, MEDIA_ROOT / 'photos' / 'features')
                    success_msgs.append(f'✅ Feature photos saved: {count} images')
                except Exception as e:
                    error_msgs.append(f'❌ Feature photos error: {e}')

            # passing place photos — multiple files or zip
            pp_files = request.FILES.getlist('pp_photos')
            if pp_files:
                try:
                    count = save_photos(pp_files, MEDIA_ROOT / 'photos' / 'passing_places')
                    success_msgs.append(f'✅ Passing place photos saved: {count} images')
                except Exception as e:
                    error_msgs.append(f'❌ Passing place photos error: {e}')

            for msg in success_msgs:
                messages.success(request, msg)
            for msg in error_msgs:
                messages.error(request, msg)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload Route Data',
        }
        return render(request, 'admin/survey/upload_route.html', context)

    # ── Delete route files ───────────────────────────────────────────────────────
    def delete_route_view(self, request):
        import os
        from django.conf import settings
        DATA_DIR = settings.DATA_DIR

        routes = scan_routes()

        if request.method == 'POST':
            route_id  = request.POST.get('route_id')
            confirmed = request.POST.get('confirmed')

            if route_id and confirmed and route_id in routes:
                info    = routes[route_id]
                deleted = []

                # Delete xlsx
                try:
                    os.remove(info['xlsx'])
                    deleted.append(os.path.basename(info['xlsx']))
                except Exception as e:
                    messages.error(request, f'❌ Could not delete xlsx: {e}')

                # Delete dxf if exists
                if info['dxf']:
                    try:
                        os.remove(info['dxf'])
                        deleted.append(os.path.basename(info['dxf']))
                    except Exception as e:
                        messages.error(request, f'❌ Could not delete dxf: {e}')

                if deleted:
                    messages.success(request, f'✅ Deleted {route_id}: {", ".join(deleted)}')

                return redirect('/admin/survey/mapgenerationlog/delete-route/')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Delete Route Files',
            'routes': routes,
        }
        return render(request, 'admin/survey/delete_route.html', context)

    # ── Delete route photos ───────────────────────────────────────────────────────
    def delete_photos_view(self, request):
        import os
        import pandas as pd
        from django.conf import settings
        MEDIA_ROOT = settings.MEDIA_ROOT

        routes      = scan_routes()
        photo_preview = None

        if request.method == 'POST':
            route_id  = request.POST.get('route_id')
            confirmed = request.POST.get('confirmed')
            action    = request.POST.get('action')

            if route_id and route_id in routes:
                info = routes[route_id]
                try:
                    df_f  = pd.read_excel(info['xlsx'], sheet_name='Features')
                    df_pp = pd.read_excel(info['xlsx'], sheet_name='Passing Places')

                    feat_photos = [
                        str(p).strip() for p in df_f['Photo'].dropna()
                        if str(p).strip()
                    ]
                    pp_photos = [
                        str(p).strip() for p in df_pp['Photo'].dropna()
                        if str(p).strip()
                    ]
                    # Handle comma-separated multiple photos
                    feat_files = []
                    for p in feat_photos:
                        feat_files.extend([x.strip() for x in p.split(',')])
                    pp_files = []
                    for p in pp_photos:
                        pp_files.extend([x.strip() for x in p.split(',')])

                    if action == 'preview':
                        feat_exist = [f for f in feat_files if (MEDIA_ROOT / 'photos' / 'features' / f).exists()]
                        pp_exist   = [f for f in pp_files   if (MEDIA_ROOT / 'photos' / 'passing_places' / f).exists()]
                        photo_preview = {
                            'route_id':   route_id,
                            'feat_files': feat_files,
                            'pp_files':   pp_files,
                            'feat_exist': feat_exist,
                            'pp_exist':   pp_exist,
                            'total':      len(feat_exist) + len(pp_exist),
                        }

                    elif action == 'delete' and confirmed:
                        deleted = 0
                        for f in feat_files:
                            path = MEDIA_ROOT / 'photos' / 'features' / f
                            if path.exists():
                                os.remove(path)
                                deleted += 1
                        for f in pp_files:
                            path = MEDIA_ROOT / 'photos' / 'passing_places' / f
                            if path.exists():
                                os.remove(path)
                                deleted += 1
                        messages.success(request, f'✅ Deleted {deleted} photos for {route_id}')
                        return redirect('/admin/survey/mapgenerationlog/delete-photos/')

                except Exception as e:
                    messages.error(request, f'❌ Error reading route data: {e}')

        context = {
            **self.admin_site.each_context(request),
            'title':         'Delete Route Photos',
            'routes':        routes,
            'photo_preview': photo_preview,
        }
        return render(request, 'admin/survey/delete_photos.html', context)

    # ── Overview: list all routes with status ─────────────────────────────────
    def generate_overview_view(self, request):
        routes = scan_routes()
        logs   = {log.route_id: log for log in MapGenerationLog.objects.all()}

        route_status = []
        for route_id, info in routes.items():
            log = logs.get(route_id)
            route_status.append({
                "route_id": route_id,
                "label":    info["label"],
                "log":      log,
            })

        context = {
            **self.admin_site.each_context(request),
            "title":         "Generate Aerial Maps",
            "route_status":  route_status,
        }
        return render(request, "admin/survey/generate_overview.html", context)

    # ── Single route generation ───────────────────────────────────────────────
    def generate_route_view(self, request, route_id):
        routes = scan_routes()

        if route_id not in routes:
            messages.error(request, f"Route '{route_id}' not found in /data folder.")
            return redirect("admin:survey_generate_overview")

        force = request.POST.get("force") == "1"

        if request.method == "POST":
            info = routes[route_id]

            try:
                df_features, df_pp, _ = load_route_data(info["xlsx"])
            except Exception as exc:
                messages.error(request, f"Could not load data for {route_id}: {exc}")
                return redirect("admin:survey_generate_overview")

            if force:
                deleted = clear_route_cache(route_id)
                if deleted:
                    messages.info(request, f"Cleared {deleted} cached images for {route_id}.")

            tour = build_tour(df_features, df_pp)
            route_coords = get_alignment_coords(info, df_features)

            ok   = 0
            fail = 0
            t0   = time.time()

            for stop in tour:
                try:
                    maps = get_stop_maps(route_id, stop, route_coords)
                    if maps["overview_url"] and maps["detail_url"]:
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1

            duration = time.time() - t0

            # Save / update log record
            MapGenerationLog.objects.update_or_create(
                route_id=route_id,
                defaults={
                    "total_stops":   len(tour),
                    "success_count": ok,
                    "fail_count":    fail,
                    "duration_secs": round(duration, 1),
                },
            )

            if fail == 0:
                messages.success(
                    request,
                    f"✅  {route_id}: {ok} stops generated successfully in {duration:.0f}s."
                )
            else:
                messages.warning(
                    request,
                    f"⚠️  {route_id}: {ok} ok, {fail} failed. Check GPS coordinates for missing stops."
                )

            return redirect("admin:survey_generate_overview")

        # GET — confirmation page
        info = routes[route_id]
        log  = MapGenerationLog.objects.filter(route_id=route_id).first()
        context = {
            **self.admin_site.each_context(request),
            "title":    f"Generate Maps — {route_id}",
            "route_id": route_id,
            "info":     info,
            "log":      log,
        }
        return render(request, "admin/survey/generate_confirm.html", context)

    # ── List display helpers ──────────────────────────────────────────────────
    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            "ok":      ("#27ae60", "✅ OK"),
            "partial": ("#f39c12", "⚠ Partial"),
            "failed":  ("#e74c3c", "✗ Failed"),
            "unknown": ("#888",    "— Unknown"),
        }
        colour, label = colours.get(obj.status, ("#888", "—"))
        return format_html(
            '<span style="color:{}; font-weight:600">{}</span>', colour, label
        )

    @admin.display(description="Time")
    def duration_display(self, obj):
        return f"{obj.duration_secs:.0f}s" if obj.duration_secs else "—"

    @admin.display(description="")
    def generate_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Regenerate</a>',
            f"/admin/survey/mapgenerationlog/generate/{obj.route_id}/",
        )
