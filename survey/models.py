"""
survey/models.py
"""
from django.db import models


class MapGenerationLog(models.Model):
    route_id      = models.CharField(max_length=50, unique=True)
    generated_at  = models.DateTimeField(auto_now=True)
    total_stops   = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    fail_count    = models.IntegerField(default=0)
    duration_secs = models.FloatField(default=0.0)

    class Meta:
        verbose_name        = "Map Generation Log"
        verbose_name_plural = "Map Generation Logs"
        ordering            = ["route_id"]

    def __str__(self):
        return (
            f"{self.route_id} — "
            f"{self.success_count}/{self.total_stops} stops — "
            f"{self.generated_at.strftime('%d %b %Y %H:%M')}"
        )

    @property
    def status(self):
        if self.total_stops == 0:
            return "unknown"
        if self.fail_count == 0:
            return "ok"
        if self.success_count == 0:
            return "failed"
        return "partial"


class AccessLog(models.Model):
    timestamp  = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path       = models.CharField(max_length=500)
    route_id   = models.CharField(max_length=50, blank=True, null=True)
    page       = models.CharField(max_length=100, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    method     = models.CharField(max_length=10, default='GET')

    class Meta:
        verbose_name        = "Access Log"
        verbose_name_plural = "Access Logs"
        ordering            = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp.strftime('%d %b %Y %H:%M')} — {self.ip_address} — {self.page}"
