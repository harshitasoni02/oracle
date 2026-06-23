# backend/oracle/services/prediction_verification.py
"""
Prediction Verification Engine
═══════════════════════════════════════════════════════════════════════════════
Compares stored Prediction records against actual prices once the target date
has elapsed, then stores the results in PredictionVerification.

Metrics computed
────────────────
MAE   – Mean Absolute Error          (avg of |predicted - actual|)
RMSE  – Root Mean Squared Error      (sqrt of avg squared error)
MAPE  – Mean Absolute Percentage Error (avg of |error| / actual * 100)
DA    – Directional Accuracy         (% of times direction was correct)

Usage
─────
    from oracle.services.prediction_verification import verify_predictions
    stats = verify_predictions(metal="gold", timeframe="1d")
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import pandas as pd

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
    mae: float              # Mean Absolute Error (USD)
    rmse: float             # Root Mean Squared Error (USD)
    mape: float             # Mean Absolute Percentage Error (%)
    directional_accuracy: float  # % direction-correct predictions
    avg_overestimate: float      # positive = predicted too high
    recent_mae: float            # MAE on the last 30 verified records


# ─────────────────────────────────────────────────────────────────────────────
# Horizon → timedelta mapping
# ─────────────────────────────────────────────────────────────────────────────

HORIZON_DELTA = {
    "1m":  timedelta(minutes=1),
    "5m":  timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h":  timedelta(hours=1),
    "1d":  timedelta(days=1),
    "1w":  timedelta(days=7),
    "1mo": timedelta(days=30),
}


def _closest_bar_price(metal: str, timeframe: str, target_dt: datetime) -> Optional[float]:
    """
    Find the closing price of the bar closest to target_dt.
    Looks in a ±2-period window to handle weekends/gaps.
    """
    delta = HORIZON_DELTA.get(timeframe, timedelta(days=1))
    window_start = target_dt - delta * 2
    window_end = target_dt + delta * 2

    bar = (
        PriceBar.objects
        .filter(
            metal=metal,
            timeframe=timeframe,
            timestamp__gte=window_start,
            timestamp__lte=window_end,
        )
        .order_by("timestamp")
        .values("close_usd", "timestamp")
        .first()
    )
    return float(bar["close_usd"]) if bar else None


# ─────────────────────────────────────────────────────────────────────────────
# Core verification function
# ─────────────────────────────────────────────────────────────────────────────

def verify_predictions(
    metal: str = "gold",
    timeframe: str = "1d",
    limit: int = 500,
) -> VerificationStats:
    """
    Verify all unverified Prediction records whose target date has passed.

    1. Queries Prediction for unverified records (those not yet in
       PredictionVerification).
    2. For each, tries to find the actual closing price at the target time.
    3. Creates a PredictionVerification record.
    4. Returns aggregate statistics.
    """
    now = datetime.now(tz=timezone.utc)

    # Predictions already verified (avoid re-processing)
    already_verified = set(
        PredictionVerification.objects
        .filter(metal=metal, timeframe=timeframe)
        .values_list("prediction_date", flat=True)
    )

    # Unverified predictions whose target has passed
    delta = HORIZON_DELTA.get(timeframe, timedelta(days=1))
    cutoff = now - delta  # target must be in the past

    predictions = (
        Prediction.objects
.filter(
    metal=metal,
    timeframe=timeframe,
    generated_at__lte=cutoff
)
    )

    new_records: List[PredictionVerification] = []
    skipped = 0

    for pred in predictions:
        pred_dt = pred.generated_at
        target_dt = pred_dt + delta

        if pred_dt in already_verified:
            skipped += 1
            continue

        actual_price = _closest_bar_price(metal, timeframe, target_dt)
        if actual_price is None:
            logger.debug(
                "No actual price found for %s/%s target=%s",
                metal, timeframe, target_dt
            )
            continue

        # Determine directions
        prev_price = _closest_bar_price(metal, timeframe, pred_dt - delta)
        if prev_price is None:
            prev_price = pred.predicted_usd  # fallback: compare against itself

        change_pct = ((actual_price - prev_price) / prev_price) * 100

        if change_pct > 0.25:
            actual_dir = "up"
        elif change_pct < -0.25:
             actual_dir = "down"
        else:
             actual_dir = "sideways"

        predicted_dir = getattr(pred, "direction", None)
        if predicted_dir is None:
            # Infer from predicted_usd vs price at prediction time
            base_price = _closest_bar_price(metal, timeframe, pred_dt)
            if base_price:
                    pred_change_pct = ( (pred.predicted_usd - base_price) / base_price) * 100

                    if pred_change_pct > 0.25:
                         
                            predicted_dir = "up"
                    elif pred_change_pct < -0.25:
                            predicted_dir = "down"
                    else:
                             predicted_dir = "sideways"

        verification = PredictionVerification(
            metal=metal,
            timeframe=timeframe,
            prediction_date=pred_dt,
            target_date=target_dt,
            predicted_price=float(pred.predicted_usd),
            actual_price=actual_price,
            predicted_direction=predicted_dir,
            actual_direction=actual_dir,
        )
        logger.info(
                 f"Predicted={predicted_dir} "
                f"Actual={actual_dir} "
                f"Change={change_pct:.2f}%"
        )
        # save() auto-computes absolute_error, percentage_error, direction_correct
        new_records.append(verification)

        if new_records:

            for verification in new_records:
                    
                    verification.save()

        logger.info(
            "Created %d new PredictionVerification records for %s/%s",
            len(new_records), metal, timeframe,
        )

    # ── Aggregate stats ───────────────────────────────────────────────────────
    return compute_verification_stats(metal=metal, timeframe=timeframe)


def compute_verification_stats(
    metal: str, timeframe: str
) -> VerificationStats:
    """
    Compute MAE, RMSE, MAPE, Directional Accuracy from stored verifications.
    """
    records = list(
        PredictionVerification.objects
        .filter(metal=metal, timeframe=timeframe)
        .values(
            "absolute_error",
            "percentage_error",
            "direction_correct",
            "predicted_price",
            "actual_price",
        )
    )

    if not records:
        return VerificationStats(
            metal=metal, timeframe=timeframe,
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
        timeframe=timeframe,
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
    timeframes = ["1d", "1w", "1mo"]
    results = {}
    for metal in metals:
        for timeframe in timeframes:
            key = f"{metal}/{timeframe}"
            try:
                results[key] = verify_predictions(metal=metal, timeframe=timeframe)
            except Exception as exc:
                logger.error("Verification failed for %s: %s", key, exc)
    return results
