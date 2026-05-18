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
