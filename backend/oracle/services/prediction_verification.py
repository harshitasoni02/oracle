# backend/oracle/services/prediction_verification.py
"""
Prediction Verification Engine
═══════════════════════════════════════════════════════════════════════════════
Automatically verifies 1-day and 1-week predictions against actual market prices.

Flow:
  1. Celery beat runs verify_scheduled_predictions every minute.
  2. For each Prediction whose target_date has passed:
     - Look up the actual price from PriceBar (1d bars).
     - Compute absolute_error, percentage_error, direction_correct.
     - Create a PredictionVerification record (dedup by unique key).
  3. Compute aggregate stats: MAE, RMSE, MAPE, Directional Accuracy.

Supported timeframes: 1d, 1w only.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional

from django.db.models import Count, Q
from django.utils import timezone

from oracle.models import Prediction, PredictionVerification, PriceBar

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class VerificationStats:
    metal: str
    timeframe: str
    total_verified: int
    mae: float  # Mean Absolute Error (USD)
    rmse: float  # Root Mean Squared Error (USD)
    mape: float  # Mean Absolute Percentage Error (%)
    directional_accuracy: float  # % direction-correct predictions
    avg_overestimate: float  # positive = predicted too high
    recent_mae: float  # MAE on the last 30 verified records


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _classify_direction(change_pct: float) -> str:
    """Classify market direction from a percentage change."""
    if change_pct > 0.25:
        return "up"
    elif change_pct < -0.25:
        return "down"
    else:
        return "sideways"


def _is_earliest_prediction_of_day(pred) -> bool:
    """
    Check whether *pred* is the earliest Prediction generated on its
    calendar date for the same (metal, timeframe).

    Only the earliest prediction each calendar day is considered the
    "official" prediction for backtesting purposes.  All later predictions
    from the same day are ignored when creating verification records.
    """
    day_start = pred.generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    earliest = (
        Prediction.objects.filter(
            metal=pred.metal,
            timeframe=pred.timeframe,
            generated_at__gte=day_start,
            generated_at__lt=day_end,
        )
        .order_by("generated_at")
        .first()
    )
    if earliest is None:
        return True  # no other predictions — this one is the earliest by default
    return earliest.pk == pred.pk


def _has_verification_for_date(metal: str, timeframe: str, date_dt) -> bool:
    """
    Check if a PredictionVerification already exists for the given
    (metal, timeframe, calendar date).  Returns True if one exists.
    """
    day_start = date_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return PredictionVerification.objects.filter(
        metal=metal,
        timeframe=timeframe,
        prediction_date__gte=day_start,
        prediction_date__lt=day_end,
    ).exists()


def _get_actual_price(metal: str, target_dt) -> Optional[float]:
    """
    Find the closing price of the 1d PriceBar closest to target_dt.
    Uses 1d bars since they are the most reliable source.
    """
    window_start = target_dt - timedelta(days=2)
    window_end = target_dt + timedelta(days=2)

    bars = list(
        PriceBar.objects.filter(
            metal=metal,
            timeframe="1d",
            timestamp__gte=window_start,
            timestamp__lte=window_end,
        ).values("close_usd", "timestamp")
    )
    if not bars:
        return None
    closest = min(bars, key=lambda b: abs(b["timestamp"] - target_dt))
    return float(closest["close_usd"])


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup helpers
# ─────────────────────────────────────────────────────────────────────────────


def cleanup_bad_verifications() -> int:
    """
    Delete PredictionVerification records with previous_price = 0.
    Returns the number of records deleted.
    """
    count = PredictionVerification.objects.filter(previous_price=0).count()
    if count:
        PredictionVerification.objects.filter(previous_price=0).delete()
        logger.warning("Cleaned up %d bad Verification records (previous_price=0)", count)
    return count


def deduplicate_verifications() -> int:
    """
    Keep only the first Verification record for each (metal, timeframe,
    prediction_date, target_date) combination. Delete the rest.
    Returns the number of records deleted.
    """
    dup_keys = (
        PredictionVerification.objects.filter(timeframe__in=["1d", "1w"])
        .values("metal", "timeframe", "prediction_date", "target_date")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )

    deleted = 0
    for key in dup_keys:
        records = PredictionVerification.objects.filter(
            metal=key["metal"],
            timeframe=key["timeframe"],
            prediction_date=key["prediction_date"],
            target_date=key["target_date"],
        ).order_by("id")

        if records.count() > 1:
            keep = records.first()
            to_delete = records.exclude(id=keep.id)
            deleted += to_delete.count()
            to_delete.delete()

    if deleted > 0:
        logger.warning("Deduplicated: removed %d duplicate Verification records", deleted)
    return deleted


def _backfill_old_predictions():
    """
    For existing 1d/1w predictions that have previous_price_usd=0 or target_date=None,
    backfill them from the current PriceSnapshot and compute target_date.
    """
    horizon_map = {
        "1d": timedelta(days=1),
        "1w": timedelta(days=7),
    }

    updated = 0
    for pred in Prediction.objects.filter(
        timeframe__in=["1d", "1w"],
    ).filter(
        Q(previous_price_usd=0) | Q(target_date__isnull=True)
    ):
        # Backfill previous_price_usd from current_price_usd if missing
        if pred.previous_price_usd == 0 and pred.current_price_usd > 0:
            pred.previous_price_usd = pred.current_price_usd

        # Backfill target_date if missing
        if pred.target_date is None:
            delta = horizon_map.get(pred.timeframe, timedelta(days=1))
            pred.target_date = pred.generated_at + delta

        pred.save(update_fields=["previous_price_usd", "target_date"])
        updated += 1

    if updated > 0:
        logger.info("Backfilled %d old predictions with previous_price_usd and target_date", updated)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled verification (runs every minute via Celery beat)
# ─────────────────────────────────────────────────────────────────────────────

def verify_scheduled_predictions():
    """
    Find all 1d and 1w predictions whose target_date has passed,
    and create PredictionVerification records for them.
    Skips predictions that already have a verification record (dedup).
    Runs cleanup on every invocation to remove stale records.
    """
    now = timezone.now()

    # 1. Clean up bad records (previous_price=0)
    cleanup_bad_verifications()

    # 2. Deduplicate existing verifications
    deduplicate_verifications()

    # 3. Backfill old predictions that don't have previous_price_usd or target_date
    _backfill_old_predictions()

    # 4. Verify predictions whose target_date has passed
    predictions = (
        Prediction.objects.filter(
            timeframe__in=["1d", "1w"],
            target_date__lte=now,
            previous_price_usd__gt=0,
        )
        .order_by("target_date")
    )

    created = 0
    skipped = 0

    for pred in predictions:
        # Only ONE verification per (metal, timeframe, calendar date).
        # If a verification already exists for this prediction's date, skip.
        if _has_verification_for_date(pred.metal, pred.timeframe, pred.generated_at):
            skipped += 1
            continue

        # Dedup: check if verification already exists for this exact prediction
        exists = PredictionVerification.objects.filter(
            metal=pred.metal,
            timeframe=pred.timeframe,
            prediction_date=pred.generated_at,
            target_date=pred.target_date,
        ).exists()
        if exists:
            skipped += 1
            continue

        actual_price = _get_actual_price(pred.metal, pred.target_date)
        if actual_price is None:
            logger.debug(
                "No actual price found for %s/%s target=%s",
                pred.metal, pred.timeframe, pred.target_date,
            )
            continue

        previous_price = pred.previous_price_usd
        if previous_price is None or previous_price == 0:
            previous_price = pred.current_price_usd
        if previous_price is None or previous_price == 0:
            logger.warning(
                "Skipping prediction %s/%s target=%s — no previous_price",
                pred.metal, pred.timeframe, pred.target_date,
            )
            continue

        change_pct = ((actual_price - previous_price) / previous_price) * 100
        actual_dir = _classify_direction(change_pct)

        # Predicted direction from the prediction record
        predicted_dir = pred.direction if pred.direction else "up"

        verification = PredictionVerification(
            metal=pred.metal,
            timeframe=pred.timeframe,
            prediction_date=pred.generated_at,
            target_date=pred.target_date,
            previous_price=float(previous_price),
            predicted_price=float(pred.predicted_usd),
            actual_price=actual_price,
            predicted_direction=predicted_dir,
            actual_direction=actual_dir,
        )

        logger.info(
            f"[VERIFY] {pred.metal}/{pred.timeframe} | "
            f"Prev={previous_price:.2f} | "
            f"Pred={pred.predicted_usd:.2f} | "
            f"Actual={actual_price:.2f} | "
            f"Change={change_pct:.2f}% | "
            f"PredDir={predicted_dir} | "
            f"ActDir={actual_dir}"
        )

        verification.save()
        created += 1

    if created > 0:
        logger.info(
            "Created %d new PredictionVerification records, skipped %d",
            created, skipped,
        )

    return created


# ─────────────────────────────────────────────────────────────────────────────
# Manual verification (for API trigger)
# ─────────────────────────────────────────────────────────────────────────────


def verify_predictions(
    metal: str = "gold",
    timeframe: str = "1d",
    limit: int = 500,
) -> VerificationStats:
    """
    Verify all unverified Prediction records whose target date has passed.
    This is the manual/triggered entry point.
    """
    now = timezone.now()

    # Only 1d and 1w
    if timeframe not in ("1d", "1w"):
        return VerificationStats(
            metal=metal, timeframe=timeframe,
            total_verified=0, mae=0.0, rmse=0.0, mape=0.0,
            directional_accuracy=0.0, avg_overestimate=0.0, recent_mae=0.0,
        )

    # Clean up and dedup first
    cleanup_bad_verifications()
    deduplicate_verifications()
    _backfill_old_predictions()

    predictions = (
        Prediction.objects.filter(
            metal=metal,
            timeframe=timeframe,
            target_date__lte=now,
            previous_price_usd__gt=0,
        )
        .order_by("target_date")
    )

    created = 0
    for pred in predictions:
        # Only the earliest prediction each calendar day is the "official" one
        if not _is_earliest_prediction_of_day(pred):
            continue

        # Dedup
        if PredictionVerification.objects.filter(
            metal=pred.metal,
            timeframe=pred.timeframe,
            prediction_date=pred.generated_at,
            target_date=pred.target_date,
        ).exists():
            continue

        actual_price = _get_actual_price(pred.metal, pred.target_date)
        if actual_price is None:
            continue

        previous_price = pred.previous_price_usd
        if previous_price is None or previous_price == 0:
            previous_price = pred.current_price_usd
        if previous_price is None or previous_price == 0:
            continue

        change_pct = ((actual_price - previous_price) / previous_price) * 100
        actual_dir = _classify_direction(change_pct)
        predicted_dir = pred.direction if pred.direction else "up"

        verification = PredictionVerification(
            metal=pred.metal,
            timeframe=pred.timeframe,
            prediction_date=pred.generated_at,
            target_date=pred.target_date,
            previous_price=float(previous_price),
            predicted_price=float(pred.predicted_usd),
            actual_price=actual_price,
            predicted_direction=predicted_dir,
            actual_direction=actual_dir,
        )
        logger.info(
            f"[VERIFY] {pred.metal}/{pred.timeframe} | "
            f"Prev={previous_price:.2f} | "
            f"Pred={pred.predicted_usd:.2f} | "
            f"Actual={actual_price:.2f} | "
            f"Change={change_pct:.2f}% | "
            f"PredDir={predicted_dir} | "
            f"ActDir={actual_dir}"
        )
        verification.save()
        created += 1

    if created > 0:
        logger.info("Created %d new PredictionVerification records for %s/%s", created, metal, timeframe)

    return compute_verification_stats(metal=metal, timeframe=timeframe)


# ─────────────────────────────────────────────────────────────────────────────
# Stats computation
# ─────────────────────────────────────────────────────────────────────────────


def compute_verification_stats(
    metal: str, timeframe: Optional[str] = None
) -> VerificationStats:
    """
    Compute MAE, RMSE, MAPE, Directional Accuracy from stored verifications.
    When timeframe is None, aggregates across ALL timeframes for the given metal.
    """
    q = PredictionVerification.objects.filter(metal=metal)
    if timeframe is not None:
        q = q.filter(timeframe=timeframe)
    records = list(
        q.values(
            "absolute_error",
            "percentage_error",
            "direction_correct",
            "predicted_price",
            "actual_price",
        )
        .order_by("created_at")
    )

    tf_label = timeframe if timeframe is not None else "all"

    if not records:
        return VerificationStats(
            metal=metal, timeframe=tf_label,
            total_verified=0,
            mae=0.0, rmse=0.0, mape=0.0,
            directional_accuracy=0.0,
            avg_overestimate=0.0,
            recent_mae=0.0,
        )

    abs_errors = [r["absolute_error"] for r in records]
    pct_errors = [r["percentage_error"] for r in records]
    directions = [r["direction_correct"] for r in records]
    price_diffs = [r["predicted_price"] - r["actual_price"] for r in records]

    mae = sum(abs_errors) / len(abs_errors)
    rmse = math.sqrt(sum(e ** 2 for e in abs_errors) / len(abs_errors))
    mape = sum(pct_errors) / len(pct_errors)
    directional_accuracy = sum(directions) / len(directions) * 100
    avg_overestimate = sum(price_diffs) / len(price_diffs)

    recent = abs_errors[-30:] if len(abs_errors) >= 30 else abs_errors
    recent_mae = sum(recent) / len(recent)

    return VerificationStats(
        metal=metal,
        timeframe=tf_label,
        total_verified=len(records),
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        mape=round(mape, 4),
        directional_accuracy=round(directional_accuracy, 2),
        avg_overestimate=round(avg_overestimate, 4),
        recent_mae=round(recent_mae, 4),
    )


def run_full_verification() -> Dict[str, VerificationStats]:
    """Run verification for all metal × timeframe combinations."""
    metals = ["gold", "silver"]
    timeframes = ["1d", "1w"]
    results = {}
    for metal in metals:
        for timeframe in timeframes:
            key = f"{metal}/{timeframe}"
            try:
                results[key] = verify_predictions(metal=metal, timeframe=timeframe)
            except Exception as exc:
                logger.error("Verification failed for %s: %s", key, exc)
    return results