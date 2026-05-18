from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MapGenerationLog",
            fields=[
                ("id",            models.BigAutoField(auto_created=True, primary_key=True)),
                ("route_id",      models.CharField(max_length=50, unique=True)),
                ("generated_at",  models.DateTimeField(auto_now=True)),
                ("total_stops",   models.IntegerField(default=0)),
                ("success_count", models.IntegerField(default=0)),
                ("fail_count",    models.IntegerField(default=0)),
                ("duration_secs", models.FloatField(default=0.0)),
            ],
            options={
                "verbose_name":        "Map Generation Log",
                "verbose_name_plural": "Map Generation Logs",
                "ordering":            ["route_id"],
            },
        ),
    ]
