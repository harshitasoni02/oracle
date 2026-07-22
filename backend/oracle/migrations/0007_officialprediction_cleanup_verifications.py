# Generated manually to fix daily official prediction verification.

from django.db import migrations, models
from django.utils import timezone


def cleanup_verification_history(apps, schema_editor):
    PredictionVerification = apps.get_model("oracle", "PredictionVerification")

    PredictionVerification.objects.filter(
        timeframe__in=["1d", "1w"],
        target_date__gt=timezone.now(),
    ).delete()

    seen = set()
    records = (
        PredictionVerification.objects.filter(timeframe__in=["1d", "1w"])
        .order_by("metal", "timeframe", "prediction_date", "id")
        .values("id", "metal", "timeframe", "prediction_date")
    )
    duplicate_ids = []
    for record in records:
        key = (
            record["metal"],
            record["timeframe"],
            record["prediction_date"].date(),
        )
        if key in seen:
            duplicate_ids.append(record["id"])
        else:
            seen.add(key)

    if duplicate_ids:
        PredictionVerification.objects.filter(id__in=duplicate_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("oracle", "0006_prediction_previous_price_usd_prediction_target_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficialPrediction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("metal", models.CharField(choices=[("gold", "Gold"), ("silver", "Silver")], db_index=True, max_length=10)),
                ("timeframe", models.CharField(choices=[("1d", "1 Day"), ("1w", "1 Week")], db_index=True, max_length=5)),
                ("prediction_day", models.DateField(db_index=True)),
                ("prediction_date", models.DateTimeField(db_index=True)),
                ("target_date", models.DateTimeField(db_index=True)),
                ("previous_price_usd", models.FloatField(default=0)),
                ("predicted_usd", models.FloatField(default=0)),
                ("predicted_direction", models.CharField(choices=[("up", "Bullish"), ("down", "Bearish"), ("sideways", "Sideways")], default="sideways", max_length=10)),
                ("signal_label", models.CharField(default="Neutral", max_length=20)),
                ("confidence", models.IntegerField(default=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-prediction_date"],
                "unique_together": {("metal", "timeframe", "prediction_day")},
            },
        ),
        migrations.RunPython(cleanup_verification_history, migrations.RunPython.noop),
    ]
