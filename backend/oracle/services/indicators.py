"""
Technical indicator computations (pure pandas/numpy — no external TA library).
All functions accept a pandas DataFrame with columns: Open, High, Low, Close, Volume.
"""
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger('oracle')


# ─────────────────────────────── Trend ────────────────────────────────

def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(window=n, min_periods=n).mean()


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False, min_periods=n).mean()


# ─────────────────────────────── Momentum ──────────────────────────────

def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=n - 1, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(com=n - 1, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def macd(series: pd.Series, fast=12, slow=26, signal=9):
    """Returns (macd_line, signal_line, histogram)."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period=14, d_period=3):
    """Returns (%K, %D)."""
    lowest_low = low.rolling(k_period, min_periods=k_period).min()
    highest_high = high.rolling(k_period, min_periods=k_period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    k = 100.0 * (close - lowest_low) / denom
    d = k.rolling(d_period).mean()
    return k, d


def cci(high: pd.Series, low: pd.Series, close: pd.Series, n=20) -> pd.Series:
    typical = (high + low + close) / 3.0
    sma_tp = typical.rolling(n, min_periods=n).mean()
    mad = typical.rolling(n, min_periods=n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (typical - sma_tp) / (0.015 * mad.replace(0, np.nan))


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, n=14) -> pd.Series:
    highest_high = high.rolling(n, min_periods=n).max()
    lowest_low = low.rolling(n, min_periods=n).min()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    return -100.0 * (highest_high - close) / denom


# ─────────────────────────────── Volatility ────────────────────────────

def bollinger_bands(series: pd.Series, n=20, k=2.0):
    """Returns (upper, middle, lower)."""
    middle = sma(series, n)
    std = series.rolling(n, min_periods=n).std()
    upper = middle + k * std
    lower = middle - k * std
    return upper, middle, lower


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n=14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(com=n - 1, adjust=False, min_periods=n).mean()


# ─────────────────────────────── Volume ────────────────────────────────

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


# ─────────────────────────────── Signal Scoring ────────────────────────

def _score_rsi(val):
    if val is None or np.isnan(val):
        return None, 'N/A'
    if val < 25:
        return 1.0, 'Strong Buy'
    if val < 35:
        return 0.7, 'Buy'
    if val < 45:
        return 0.3, 'Weak Buy'
    if val < 55:
        return 0.0, 'Neutral'
    if val < 65:
        return -0.3, 'Weak Sell'
    if val < 75:
        return -0.7, 'Sell'
    return -1.0, 'Strong Sell'


def _score_macd(macd_val, signal_val, hist_val):
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in [macd_val, signal_val, hist_val]):
        return None, 'N/A'
    if macd_val > signal_val and hist_val > 0:
        return 1.0, 'Strong Buy'
    if macd_val > signal_val:
        return 0.5, 'Buy'
    if macd_val < signal_val and hist_val < 0:
        return -1.0, 'Strong Sell'
    return -0.5, 'Sell'


def _score_stochastic(k_val):
    if k_val is None or np.isnan(k_val):
        return None, 'N/A'
    if k_val < 20:
        return 1.0, 'Strong Buy'
    if k_val < 35:
        return 0.5, 'Buy'
    if k_val < 65:
        return 0.0, 'Neutral'
    if k_val < 80:
        return -0.5, 'Sell'
    return -1.0, 'Strong Sell'


def _score_cci(val):
    if val is None or np.isnan(val):
        return None, 'N/A'
    if val < -150:
        return 1.0, 'Strong Buy'
    if val < -100:
        return 0.7, 'Buy'
    if val < -50:
        return 0.3, 'Weak Buy'
    if val < 50:
        return 0.0, 'Neutral'
    if val < 100:
        return -0.3, 'Weak Sell'
    if val < 150:
        return -0.7, 'Sell'
    return -1.0, 'Strong Sell'


def _score_williams(val):
    if val is None or np.isnan(val):
        return None, 'N/A'
    if val < -80:
        return 1.0, 'Strong Buy'
    if val < -65:
        return 0.5, 'Buy'
    if val < -35:
        return 0.0, 'Neutral'
    if val < -20:
        return -0.5, 'Sell'
    return -1.0, 'Strong Sell'


def _score_bollinger(price, upper, lower):
    if any(v is None or np.isnan(v) for v in [price, upper, lower]) or upper == lower:
        return None, 'N/A'
    pct = (price - lower) / (upper - lower)
    if pct < 0.10:
        return 1.0, 'Strong Buy'
    if pct < 0.25:
        return 0.5, 'Buy'
    if pct < 0.75:
        return 0.0, 'Neutral'
    if pct < 0.90:
        return -0.5, 'Sell'
    return -1.0, 'Strong Sell'


def _score_sma_position(price, sma_val, label):
    if price is None or sma_val is None or np.isnan(sma_val):
        return None, 'N/A'
    if price > sma_val:
        return 0.5, f'Above {label}'
    return -0.5, f'Below {label}'


def _score_sma_alignment(sma20, sma50, sma200):
    if any(v is None or np.isnan(v) for v in [sma20, sma50, sma200]):
        return None, 'N/A'
    if sma20 > sma50 > sma200:
        return 1.0, 'Golden Alignment'
    if sma20 < sma50 < sma200:
        return -1.0, 'Death Alignment'
    return 0.0, 'Mixed'


def _score_sentiment(signal_score: float, signal_label: str) -> tuple:
    """
    Map SentimentSnapshot signal_label into TA-compatible label so SignalTable can render it.
    Strong Bullish → Strong Buy, Bullish → Buy, Neutral → Neutral,
    Bearish → Sell, Strong Bearish → Strong Sell.
    """
    LABEL_MAP = {
        'Strong Bullish': 'Strong Buy',
        'Bullish':        'Buy',
        'Neutral':        'Neutral',
        'Bearish':        'Sell',
        'Strong Bearish': 'Strong Sell',
    }
    return round(signal_score, 3), LABEL_MAP.get(signal_label, 'Neutral')


def compute_dji_signals(dji_df: pd.DataFrame) -> tuple:
    """
    Compute DJI-based correlation signals for gold/silver (inverse relationship).
    DJI rising (risk-on) = bearish for gold; DJI falling (risk-off) = bullish for gold.
    Returns (dji_vals dict, scores dict, signals dict).
    """
    if dji_df.empty or len(dji_df) < 15:
        return {}, {}, {}

    close = dji_df['Close']

    def _last(series):
        vals = series.dropna()
        return float(vals.iloc[-1]) if not vals.empty else None

    dji_rsi_s = rsi(close, 14)
    dji_sma20_s = sma(close, 20)
    dji_sma50_s = sma(close, 50)

    curr_close = _last(close)
    prev_close = float(close.iloc[-2]) if len(close) > 1 else curr_close
    change_pct = ((curr_close - prev_close) / prev_close * 100) if prev_close else None

    dji_vals = {
        'dji_price':      curr_close,
        'dji_change_pct': round(change_pct, 2) if change_pct is not None else None,
        'dji_rsi':        _last(dji_rsi_s),
        'dji_sma20':      _last(dji_sma20_s),
        'dji_sma50':      _last(dji_sma50_s),
    }

    scores = {}
    signals = {}

    # DJI RSI: overbought DJI → bearish gold; oversold DJI → bullish gold
    dji_rsi_val = dji_vals['dji_rsi']
    if dji_rsi_val is not None and not np.isnan(dji_rsi_val):
        if dji_rsi_val > 75:
            sc, lb = -0.8, 'DJI Overbought → Bear'
        elif dji_rsi_val > 65:
            sc, lb = -0.4, 'DJI Extended → Mild Bear'
        elif dji_rsi_val < 25:
            sc, lb = 0.8, 'DJI Oversold → Bull'
        elif dji_rsi_val < 35:
            sc, lb = 0.4, 'DJI Weak → Mild Bull'
        else:
            sc, lb = 0.0, 'DJI RSI Neutral'
        scores['dji_rsi'] = sc
        signals['dji_rsi'] = {'score': round(sc, 3), 'label': lb}

    # DJI trend vs SMA20: uptrend = risk-on = bearish gold
    price_val = dji_vals['dji_price']
    sma20_val = dji_vals['dji_sma20']
    if price_val is not None and sma20_val is not None and not np.isnan(sma20_val):
        deviation = (price_val - sma20_val) / sma20_val
        if deviation > 0.03:
            sc, lb = -0.5, 'DJI Uptrend → Risk-On'
        elif deviation < -0.03:
            sc, lb = 0.5, 'DJI Downtrend → Risk-Off'
        else:
            sc, lb = 0.0, 'DJI Near SMA20'
        scores['dji_trend'] = sc
        signals['dji_trend'] = {'score': round(sc, 3), 'label': lb}

    # DJI day change: sharp drop → flight to safety → bullish gold
    if change_pct is not None:
        if change_pct < -2.0:
            sc, lb = 0.6, 'DJI Crash → Safe Haven'
        elif change_pct < -1.0:
            sc, lb = 0.3, 'DJI Sell-off → Mild Bull'
        elif change_pct > 2.0:
            sc, lb = -0.6, 'DJI Rally → Risk-On'
        elif change_pct > 1.0:
            sc, lb = -0.3, 'DJI Rise → Mild Bear'
        else:
            sc, lb = 0.0, 'DJI Change Neutral'
        scores['dji_change'] = sc
        signals['dji_change'] = {'score': round(sc, 3), 'label': lb}

    return dji_vals, scores, signals


def _label_from_score(score: float) -> str:
    if score > 0.6:
        return 'Strong Buy'
    if score > 0.2:
        return 'Buy'
    if score > -0.2:
        return 'Neutral'
    if score > -0.6:
        return 'Sell'
    return 'Strong Sell'


# ─────────────────────────────── Main Entry ────────────────────────────

def compute_indicators(df: pd.DataFrame, dji_df: pd.DataFrame = None, sentiment_snapshot=None) -> dict:
    """
    Given a DataFrame with OHLCV columns, compute all indicators.
    Returns a flat dict of indicator values + signal scores.
    """
    if df.empty or len(df) < 15:
        return {}

    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df.get('Volume', pd.Series(0, index=df.index))

    def _last(series):
        vals = series.dropna()
        return float(vals.iloc[-1]) if not vals.empty else None

    # ── Compute series ────────────────────────────────────────────────
    sma20_s  = sma(close, 20)
    sma50_s  = sma(close, 50)
    sma200_s = sma(close, 200)
    ema12_s  = ema(close, 12)
    ema26_s  = ema(close, 26)
    ema50_s  = ema(close, 50)
    rsi_s    = rsi(close, 14)
    macd_line_s, macd_sig_s, macd_hist_s = macd(close)
    stoch_k_s, stoch_d_s = stochastic(high, low, close)
    cci_s    = cci(high, low, close, 20)
    wr_s     = williams_r(high, low, close, 14)
    bb_upper_s, bb_mid_s, bb_lower_s = bollinger_bands(close, 20, 2.0)
    atr_s    = atr(high, low, close, 14)
    obv_s    = obv(close, volume)

    # ── Extract latest values ─────────────────────────────────────────
    vals = {
        'current_price': _last(close),
        'sma20':         _last(sma20_s),
        'sma50':         _last(sma50_s),
        'sma200':        _last(sma200_s),
        'ema12':         _last(ema12_s),
        'ema26':         _last(ema26_s),
        'ema50':         _last(ema50_s),
        'rsi':           _last(rsi_s),
        'macd':          _last(macd_line_s),
        'macd_signal_line': _last(macd_sig_s),
        'macd_hist':     _last(macd_hist_s),
        'stoch_k':       _last(stoch_k_s),
        'stoch_d':       _last(stoch_d_s),
        'cci':           _last(cci_s),
        'williams_r':    _last(wr_s),
        'bb_upper':      _last(bb_upper_s),
        'bb_middle':     _last(bb_mid_s),
        'bb_lower':      _last(bb_lower_s),
        'atr':           _last(atr_s),
        'obv':           _last(obv_s),
    }

    # ── Score each indicator ──────────────────────────────────────────
    scores = {}
    signals = {}

    def add(key, score, label):
        if score is not None:
            scores[key] = score
            signals[key] = {'score': round(score, 3), 'label': label}

    sc, lb = _score_rsi(vals['rsi'])
    add('rsi', sc, lb)

    sc, lb = _score_macd(vals['macd'], vals['macd_signal_line'], vals['macd_hist'])
    add('macd', sc, lb)

    sc, lb = _score_stochastic(vals['stoch_k'])
    add('stochastic', sc, lb)

    sc, lb = _score_cci(vals['cci'])
    add('cci', sc, lb)

    sc, lb = _score_williams(vals['williams_r'])
    add('williams_r', sc, lb)

    sc, lb = _score_bollinger(vals['current_price'], vals['bb_upper'], vals['bb_lower'])
    add('bollinger', sc, lb)

    sc, lb = _score_sma_position(vals['current_price'], vals['sma20'], 'SMA20')
    add('sma20', sc, lb)

    sc, lb = _score_sma_position(vals['current_price'], vals['sma50'], 'SMA50')
    add('sma50', sc, lb)

    sc, lb = _score_sma_position(vals['current_price'], vals['sma200'], 'SMA200')
    add('sma200', sc, lb)

    sc, lb = _score_sma_alignment(vals['sma20'], vals['sma50'], vals['sma200'])
    add('sma_alignment', sc, lb)

    # ── DJI correlation signals (if available) ────────────────────────
    dji_scores = {}
    if dji_df is not None and not dji_df.empty:
        dji_vals, dji_scores, dji_signals = compute_dji_signals(dji_df)
        vals.update(dji_vals)
        scores.update(dji_scores)
        signals.update(dji_signals)

    # ── News sentiment signal (if available) ──────────────────────────
    # Stored in individual_signals for display + Buy/Neutral/Sell count,
    # but blended separately (20% weight) rather than equal-averaged with TA.
    sentiment_score_val = None
    if sentiment_snapshot is not None:
        s_score = sentiment_snapshot.signal_score
        s_label = sentiment_snapshot.signal_label
        mapped_score, mapped_label = _score_sentiment(s_score, s_label)
        signals['news_sentiment'] = {'score': mapped_score, 'label': mapped_label}
        sentiment_score_val = s_score

    # ── Composite: 80% TA+DJI average, 20% news sentiment ────────────
    # Sentiment is a fundamentally different signal class (event-driven vs
    # price-derived) so it gets a fixed weight rather than being diluted
    # across the growing pool of TA signals.
    SENTIMENT_WEIGHT = 0.20
    if scores:
        ta_composite = sum(scores.values()) / len(scores)
        ta_composite = max(-1.0, min(1.0, ta_composite))
    else:
        ta_composite = 0.0

    if sentiment_score_val is not None:
        composite = ta_composite * (1 - SENTIMENT_WEIGHT) + sentiment_score_val * SENTIMENT_WEIGHT
    else:
        composite = ta_composite
    composite = max(-1.0, min(1.0, composite))

    vals['signal_score'] = round(composite, 4)
    vals['signal_label'] = _label_from_score(composite)
    vals['individual_signals'] = signals

    return vals
