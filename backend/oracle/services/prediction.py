"""
Prediction engine:
  - Short-term (1d, 1w, 2w): signal-based using ATR for expected move size
  - Long-term (1m, 3m, 6m, 1y): linear regression on log-prices
"""
import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger('oracle')

SHORT_TERM_TIMEFRAMES = {
    '1d': 1.0,           # 1 day
    '1w': math.sqrt(5),  # 1 week ≈ √5 days
    '2w': math.sqrt(10), # 2 weeks ≈ √10 days
}

LONG_TERM_TIMEFRAMES = {
    '1m': 30,
    '3m': 90,
    '6m': 180,
    '1y': 365,
}

TIMEFRAME_LABELS = {
    '1d': 'Tomorrow',
    '1w': 'Next Week',
    '2w': 'In 2 Weeks',
    '1m': 'Next Month',
    '3m': 'In 3 Months',
    '6m': 'In 6 Months',
    '1y': 'In 1 Year',
}

# Gold seasonal bias by quarter (India festival/wedding demand effect)
# Slight positive tilt in Q3 (festival) and Q4 (wedding season)
GOLD_SEASONAL_BIAS = {1: 0.0, 2: 0.0, 3: 0.01, 4: 0.015}
SILVER_SEASONAL_BIAS = {1: 0.0, 2: 0.0, 3: 0.005, 4: 0.01}


def _direction(change_pct: float) -> str:
    if change_pct > 0.25:
        return 'up'
    if change_pct < 0.25:
        return 'down'
    return 'sideways'


def _short_term_prediction(
    current_price: float,
    atr_val: float,
    composite_score: float,
    timeframe: str,
    metal: str,
    usdinr: float,
    individual_signals: dict,
    sentiment_snapshot=None,
) -> dict:
    """Predict using technical signal composite × ATR, with sentiment confirmation."""
    tf_factor = SHORT_TERM_TIMEFRAMES[timeframe]

    # ATR as a fraction of price
    atr_pct = (atr_val / current_price) if current_price else 0.01

    # Expected % move = signal strength × ATR% × timeframe scaling × damping
    damping = 0.4  # prevent over-estimation
    expected_change_pct = composite_score * atr_pct * tf_factor * damping * 100

    predicted = current_price * (1 + expected_change_pct / 100)
    # Range = ±ATR × tf_factor × 1.5
    half_range = atr_val * tf_factor * 1.5
    pred_high = predicted + half_range
    pred_low = predicted - half_range

    # Confidence: more extreme composite = more agreement among indicators
    agreement_ratio = abs(composite_score)
    confidence = int(45 + agreement_ratio * 35)
    confidence = max(40, min(80, confidence))

    # Build rationale from top TA signals (exclude news_sentiment — handled separately below)
    signal_items = sorted(
        [(k, v) for k, v in individual_signals.items() if k != 'news_sentiment'],
        key=lambda x: abs(x[1]['score']), reverse=True,
    )
    rationale = []
    for key, info in signal_items[:5]:
        name = key.replace('_', ' ').upper()
        rationale.append(f"{name}: {info['label']}")

    # Sentiment confirmation / contradiction
    if sentiment_snapshot is not None:
        s_score = sentiment_snapshot.signal_score
        s_label = sentiment_snapshot.signal_label
        count = sentiment_snapshot.count_7d or sentiment_snapshot.count_24h
        rationale.append(f"News Sentiment ({count} articles, 7d): {s_label}")
        if abs(composite_score) > 0.05 and abs(s_score) > 0.1:
            same_direction = (composite_score > 0) == (s_score > 0)
            if same_direction:
                confidence = min(85, confidence + 5)
                rationale.append("Sentiment confirms technical signal (+confidence)")
            else:
                confidence = max(35, confidence - 5)
                rationale.append("Sentiment diverges from technicals — caution")

    return {
        'predicted_usd': round(predicted, 2),
        'predicted_high_usd': round(pred_high, 2),
        'predicted_low_usd': round(pred_low, 2),
        'predicted_inr': round(predicted * usdinr, 2),
        'predicted_high_inr': round(pred_high * usdinr, 2),
        'predicted_low_inr': round(pred_low * usdinr, 2),
        'change_pct': round(expected_change_pct, 2),
        'confidence': confidence,
        'direction': _direction(expected_change_pct),
        'rationale': rationale,
    }


def _long_term_prediction(
    df: pd.DataFrame,
    days_forward: int,
    metal: str,
    usdinr: float,
    sentiment_snapshot=None,
) -> dict:
    """Predict using linear regression on log-prices projected forward."""
    close = df['Close'].dropna()
    if len(close) < 30:
        return {}

    log_close = np.log(close.values.astype(float))
    n = len(log_close)
    t = np.arange(n, dtype=float)

    # OLS: log_price = slope * t + intercept
    A = np.vstack([t, np.ones(n)]).T
    result = np.linalg.lstsq(A, log_close, rcond=None)
    slope, intercept = result[0]

    # Residuals for uncertainty estimation
    fitted = slope * t + intercept
    residuals = log_close - fitted
    std_res = np.std(residuals)

    # Project forward
    t_future = n - 1 + days_forward
    log_pred = slope * t_future + intercept

    # Uncertainty grows with sqrt(days_forward / n)
    uncertainty = std_res * math.sqrt(days_forward / n) * 1.5

    predicted = math.exp(log_pred)
    pred_high = math.exp(log_pred + uncertainty)
    pred_low = math.exp(log_pred - uncertainty)

    current = float(close.iloc[-1])
    change_pct = (predicted - current) / current * 100

    # R² for trend quality
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((log_close - log_close.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Confidence: decays with time, improves with trend strength
    base_conf = 65 - (days_forward / 365) * 20
    confidence = int(base_conf + r2 * 12)
    confidence = max(30, min(72, confidence))

    # Seasonal bias
    from datetime import datetime, timezone
    month = datetime.now(timezone.utc).month
    quarter = (month - 1) // 3 + 1
    seasonal = GOLD_SEASONAL_BIAS.get(quarter, 0) if metal == 'gold' else SILVER_SEASONAL_BIAS.get(quarter, 0)
    predicted *= (1 + seasonal)
    pred_high *= (1 + seasonal)
    pred_low *= (1 + seasonal)
    change_pct = (predicted - current) / current * 100

    trend_label = 'Uptrend' if slope > 0 else 'Downtrend'
    daily_change = (math.exp(slope) - 1) * 100
    rationale = [
        f"Linear trend: {daily_change:+.3f}% per bar",
        f"Trend R²: {r2:.2f} ({trend_label})",
        f"Projection: {days_forward} days forward",
        f"Seasonal factor: {'+' if seasonal >= 0 else ''}{seasonal*100:.1f}% (India demand)",
        f"Uncertainty band: ±{uncertainty*100:.1f}%",
    ]

    # Add sentiment context to long-term prediction
    if sentiment_snapshot is not None:
        s_score = sentiment_snapshot.signal_score
        s_label = sentiment_snapshot.signal_label
        count = sentiment_snapshot.count_7d or sentiment_snapshot.count_24h
        rationale.append(f"News Sentiment ({count} articles, 7d): {s_label}")
        # Sentiment matters more for near-term (1m) than multi-month horizons
        if days_forward <= 30 and abs(s_score) > 0.1:
            same_direction = (change_pct > 0) == (s_score > 0)
            if same_direction:
                confidence = min(72, confidence + 3)
            else:
                confidence = max(30, confidence - 3)

    return {
        'predicted_usd': round(predicted, 2),
        'predicted_high_usd': round(pred_high, 2),
        'predicted_low_usd': round(pred_low, 2),
        'predicted_inr': round(predicted * usdinr, 2),
        'predicted_high_inr': round(pred_high * usdinr, 2),
        'predicted_low_inr': round(pred_low * usdinr, 2),
        'change_pct': round(change_pct, 2),
        'confidence': confidence,
        'direction': _direction(change_pct),
        'rationale': rationale,
    }


def generate_predictions(metal: str):
    """Generate and save all predictions for a metal."""
    from oracle.models import IndicatorSnapshot, Prediction, PriceSnapshot, SentimentSnapshot
    from oracle.services.data_fetcher import get_bars_as_dataframe

    # Get current price
    try:
        snap = PriceSnapshot.objects.get(metal=metal)
        current_price = snap.price_usd
        current_inr = snap.price_inr
        usdinr = snap.usdinr
    except PriceSnapshot.DoesNotExist:
        logger.warning(f"No price snapshot for {metal}, skipping predictions")
        return

    # Get daily indicators for short-term (already incorporates sentiment at 20% weight)
    try:
        ind = IndicatorSnapshot.objects.get(metal=metal, timeframe='1d')
        composite = ind.signal_score
        atr_val = ind.atr or (current_price * 0.01)
        ind_signals = ind.individual_signals
        signal_label = ind.signal_label
    except IndicatorSnapshot.DoesNotExist:
        composite = 0.0
        atr_val = current_price * 0.01
        ind_signals = {}
        signal_label = 'Neutral'

    # Get news sentiment snapshot (for rationale + confidence adjustment)
    try:
        sent_snap = SentimentSnapshot.objects.get(metal=metal)
    except SentimentSnapshot.DoesNotExist:
        sent_snap = None

    # Get daily bars for long-term regression
    df_daily = get_bars_as_dataframe(metal, '1d', limit=750)
    # Get weekly bars for 1Y regression
    df_weekly = get_bars_as_dataframe(metal, '1wk', limit=300)

    for tf in ['1d', '1w', '2w']:
        pred = _short_term_prediction(
            current_price, atr_val, composite, tf, metal, usdinr,
            ind_signals, sentiment_snapshot=sent_snap,
        )
        if not pred:
            continue
        Prediction.objects.update_or_create(
            metal=metal, timeframe=tf,
            defaults={
                'current_price_usd': round(current_price, 2),
                'current_price_inr': round(current_inr, 2),
                'signal_label': signal_label,
                **pred,
            }
        )

    for tf, days in LONG_TERM_TIMEFRAMES.items():
        df = df_weekly if tf == '1y' else df_daily
        pred = _long_term_prediction(df, days, metal, usdinr, sentiment_snapshot=sent_snap)
        if not pred:
            continue
        Prediction.objects.update_or_create(
            metal=metal, timeframe=tf,
            defaults={
                'current_price_usd': round(current_price, 2),
                'current_price_inr': round(current_inr, 2),
                'signal_label': signal_label,
                **pred,
            }
        )

    logger.info(f"Generated predictions for {metal}")
