"""
survey/middleware.py

Logs every page request to the AccessLog model.
Skips static files, media files and admin API calls.
"""

import re
from django.utils.deprecation import MiddlewareMixin

# Paths to ignore
IGNORE_PATTERNS = [
    r'^/static/',
    r'^/media/',
    r'^/admin/jsi18n/',
    r'^/admin/autocomplete/',
    r'^/favicon\.ico',
]

# Human-readable page names
PAGE_LABELS = {
    r'^/$':                          'Overview',
    r'^/route/[^/]+/$':             'Map & Table',
    r'^/route/[^/]+/report/$':      'Report',
    r'^/route/[^/]+/summary/$':     'Summary',
    r'^/downloads/$':               'Downloads',
    r'^/admin/':                    'Admin',
}


def _get_client_ip(request):
    """Get real client IP — checks X-Forwarded-For for proxy setups."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_route_id(path):
    """Extract route ID from URL if present."""
    m = re.match(r'^/route/([^/]+)/', path)
    return m.group(1) if m else None


def _get_page_label(path):
    """Map URL path to human-readable page name."""
    for pattern, label in PAGE_LABELS.items():
        if re.match(pattern, path):
            return label
    return path[:100]


class AccessLogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        path = request.path

        # Skip ignored paths
        for pattern in IGNORE_PATTERNS:
            if re.match(pattern, path):
                return response

        # Only log successful page loads
        if response.status_code not in (200, 302):
            return response

        try:
            from .models import AccessLog
            AccessLog.objects.create(
                ip_address = _get_client_ip(request),
                path       = path,
                route_id   = _get_route_id(path),
                page       = _get_page_label(path),
                user_agent = request.META.get('HTTP_USER_AGENT', '')[:300],
                method     = request.method,
            )
        except Exception:
            pass  # Never let logging break the app

        return response
