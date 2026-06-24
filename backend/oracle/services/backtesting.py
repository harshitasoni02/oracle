# backend/oracle/services/backtesting.py
"""
Backtesting Engine for Oracle
═══════════════════════════════════════════════════════════════════════════════
Replays historical PriceBar data through each strategy (RSI, MACD, Composite,
Sentiment) and computes performance metrics: accuracy, win-rate, profit factor,
Sharpe ratio, max drawdown, total return.

Usage
─────
    from oracle.services.backtesting import BacktestEngine
    engine = BacktestEngine(metal="gold", timeframe="1d", horizon="1w")
    results = engine.run_all()          # runs all 4 strategies
    # or
    result  = engine.run_strategy("rsi")
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from oracle.models import BacktestResult, PriceBar, SentimentSnapshot

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    """Represents a single completed trade."""
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    direction: str          # "long" | "short"
    pct_return: float = field(init=False)

    def __post_init__(self):
        if self.direction == "long":
            self.pct_return = (self.exit_price - self.entry_price) / self.entry_price * 100
        else:
            self.pct_return = (self.entry_price - self.exit_price) / self.entry_price * 100


@dataclass
class BacktestMetrics:
    """All performance metrics for one strategy run."""
    strategy: str
    metal: str
    timeframe: str
    horizon: str
    accuracy: float
    win_rate: float
    total_trades: int
    avg_gain: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    total_return: float
    start_date: Optional[date]
    end_date: Optional[date]


# ─────────────────────────────────────────────────────────────────────────────
# Indicator helpers  (self-contained so they don't depend on the live engine)
# ─────────────────────────────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def _bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return mid + std_dev * std, mid, mid - std_dev * std


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mean_dev = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())))
    return (tp - sma_tp) / (0.015 * mean_dev)


def _stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series,
    k_period: int = 14, d_period: int = 3
):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-9)
    d = k.rolling(d_period).mean()
    return k, d


# ─────────────────────────────────────────────────────────────────────────────
# Signal generators  (return pd.Series of  1=BUY  -1=SELL  0=HOLD)
# ─────────────────────────────────────────────────────────────────────────────

def _rsi_signals(df: pd.DataFrame) -> pd.Series:
    rsi = _rsi(df["close"])
    signals = pd.Series(0, index=df.index)
    signals[rsi < 30] = 1     # oversold → buy
    signals[rsi > 70] = -1    # overbought → sell
    return signals


def _macd_signals(df: pd.DataFrame) -> pd.Series:
    macd_line, signal_line, _ = _macd(df["close"])
    # Crossover: macd crosses above signal → buy; below → sell
    prev_diff = (macd_line - signal_line).shift(1)
    curr_diff = macd_line - signal_line
    signals = pd.Series(0, index=df.index)
    signals[(prev_diff < 0) & (curr_diff >= 0)] = 1
    signals[(prev_diff > 0) & (curr_diff <= 0)] = -1
    return signals


def _composite_signals(df: pd.DataFrame) -> pd.Series:
    """
    Combine RSI + MACD + Bollinger + Stochastic into a weighted vote.
    Score ≥ 2 → BUY, ≤ -2 → SELL, otherwise HOLD.
    """
    rsi = _rsi(df["close"])
    macd_line, signal_line, _ = _macd(df["close"])
    _, _, lower_bb = _bollinger(df["close"])
    k, d = _stochastic(df["high"], df["low"], df["close"])

    score = pd.Series(0.0, index=df.index)

    # RSI
    score[rsi < 30] += 1
    score[rsi > 70] -= 1

    # MACD crossover
    prev_diff = (macd_line - signal_line).shift(1)
    curr_diff = macd_line - signal_line
    score[(prev_diff < 0) & (curr_diff >= 0)] += 1
    score[(prev_diff > 0) & (curr_diff <= 0)] -= 1

    # Bollinger lower touch
    score[df["close"] < lower_bb] += 1
    score[df["close"] > lower_bb * 1.05] -= 0.5   # partial reversal

    # Stochastic
    score[k < 20] += 1
    score[k > 80] -= 1

    signals = pd.Series(0, index=df.index)
    signals[score >= 2] = 1
    signals[score <= -2] = -1
    return signals


def _sentiment_signals(df: pd.DataFrame, metal: str) -> pd.Series:
    """
    Map daily FinBERT sentiment scores onto the price bar index.
    Positive → BUY, Negative → SELL, Neutral → HOLD.
    """
    signals = pd.Series(0, index=df.index)

    sentiments = (
    SentimentSnapshot.objects
    .filter(metal=metal)
    .values("updated_at", "signal_score", "signal_label")
    .order_by("updated_at")

    )
    if not sentiments:
        return signals

    sent_df = pd.DataFrame(list(sentiments))
    sent_df["updated_at"] = pd.to_datetime(sent_df["updated_at"]).dt.normalize()
    sent_df = sent_df.set_index("updated_at")

    for idx in df.index:
        day = pd.Timestamp(idx).normalize()
        if day in sent_df.index:
            row = sent_df.loc[day]
            label = row["signal_label"] if isinstance(row, pd.Series) else row.iloc[-1]["label"]
            if label == "positive":
                signals.at[idx] = 1
            elif label == "negative":
                signals.at[idx] = -1

    return signals


# ─────────────────────────────────────────────────────────────────────────────
# Performance calculator
# ─────────────────────────────────────────────────────────────────────────────

def _compute_metrics(
    df: pd.DataFrame,
    signals: pd.Series,
    horizon_days: int,
    strategy: str,
    metal: str,
    timeframe: str,
    horizon: str,
) -> BacktestMetrics:
    """
    Given a DataFrame of OHLCV bars and a signal series,
    simulate holding for `horizon_days` after each signal fires
    and compute all performance metrics.
    """
    trades: List[Trade] = []
    close = df["close"].values
    dates = df.index.tolist()
    n = len(close)

    direction_correct = 0
    total_signals = 0

    for i, sig in enumerate(signals.values):
        if sig == 0:
            continue
        exit_i = i + horizon_days
        if exit_i >= n:
            continue

        entry_price = close[i]
        exit_price = close[exit_i]
        direction = "long" if sig == 1 else "short"

        # Directional accuracy (did price move the way signal predicted?)
        actual_up = exit_price > entry_price
        predicted_up = sig == 1
        if actual_up == predicted_up:
            direction_correct += 1
        total_signals += 1

        trade = Trade(
            entry_date=dates[i],
            exit_date=dates[exit_i],
            entry_price=entry_price,
            exit_price=exit_price,
            direction=direction,
        )
        trades.append(trade)

    if not trades:
        return BacktestMetrics(
            strategy=strategy, metal=metal, timeframe=timeframe, horizon=horizon,
            accuracy=0.0, win_rate=0.0, total_trades=0,
            avg_gain=0.0, avg_loss=0.0, profit_factor=0.0,
            max_drawdown=0.0, sharpe_ratio=0.0, total_return=0.0,
            start_date=None, end_date=None,
        )

    returns = [t.pct_return for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    avg_gain = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(abs(np.mean(losses))) if losses else 0.0

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 1e-9
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")

    win_rate = len(wins) / len(trades) * 100
    accuracy = direction_correct / total_signals * 100 if total_signals else 0.0

    # ── Equity curve for drawdown + Sharpe ──────────────────────────────────
    cumulative = 100.0
    equity_curve = [cumulative]
    for r in returns:
        cumulative *= (1 + r / 100)
        equity_curve.append(cumulative)

    equity_arr = np.array(equity_curve)
    peak = np.maximum.accumulate(equity_arr)
    drawdowns = (equity_arr - peak) / peak * 100
    max_drawdown = float(abs(np.min(drawdowns)))

    total_return = float(equity_arr[-1] - 100.0)

    # Sharpe (annualised, 252 trading days, no risk-free rate)
    ret_array = np.array(returns)
    if ret_array.std() > 0:
        periods_per_year = 252 / max(horizon_days, 1)
        sharpe = (ret_array.mean() / ret_array.std()) * math.sqrt(periods_per_year)
    else:
        sharpe = 0.0

    return BacktestMetrics(
        strategy=strategy,
        metal=metal,
        timeframe=timeframe,
        horizon=horizon,
        accuracy=round(accuracy, 2),
        win_rate=round(win_rate, 2),
        total_trades=len(trades),
        avg_gain=round(avg_gain, 4),
        avg_loss=round(avg_loss, 4),
        profit_factor=round(profit_factor, 4),
        max_drawdown=round(max_drawdown, 4),
        sharpe_ratio=round(sharpe, 4),
        total_return=round(total_return, 4),
        start_date=trades[0].entry_date if trades else None,
        end_date=trades[-1].exit_date if trades else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main engine class
# ─────────────────────────────────────────────────────────────────────────────

HORIZON_DAYS = {"1d": 1, "1w": 5, "1mo": 21}

STRATEGY_FN = {
    "rsi": _rsi_signals,
    "macd": _macd_signals,
    "composite": _composite_signals,
}


class BacktestEngine:
    """
    Orchestrates backtesting for a (metal, timeframe, horizon) combination.

    Parameters
    ----------
    metal     : "gold" | "silver"
    timeframe : "1d" | "1w" 
    horizon   : "1d" | "1w" 
    lookback  : How many bars to fetch from the DB (default 500)
    """

    def __init__(
        self,
        metal: str = "gold",
        timeframe: str = "1d",
        horizon: str = "1w",
        lookback: int = 500,
    ):
        self.metal = metal
        self.timeframe = timeframe
        self.horizon = horizon
        self.lookback = lookback
        self._df: Optional[pd.DataFrame] = None

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_df(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        
        bars = (
    PriceBar.objects
    .filter(metal=self.metal, timeframe=self.timeframe)
    .order_by("timestamp")
    .values(
        "timestamp",
        "open_usd",
        "high_usd",
        "low_usd",
        "close_usd",
        "volume"
    )
)

        if not bars:
            raise ValueError(
                f"No PriceBar data for metal={self.metal} timeframe={self.timeframe}. "
                "Run the historical data refresh first."
            )

        df = pd.DataFrame(list(bars))
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()
        df = df.astype({"open_usd": float, "high_usd": float, "low_usd": float, "close_usd": float, "volume": float})
        df = df.dropna(subset=["close_usd"]) 
        # Oracle compatibility aliases
        df["open"] = df["open_usd"]
        df["high"] = df["high_usd"]
        df["low"] = df["low_usd"]
        df["close"] = df["close_usd"]
        

        if len(df) < 30:
            raise ValueError(
                f"Insufficient data for backtesting: only {len(df)} bars. Need ≥30."
            )

        self._df = df.tail(self.lookback)
        logger.info(
            "BacktestEngine loaded %d bars for %s/%s",
            len(self._df), self.metal, self.timeframe,
        )
        return self._df

    # ── Single strategy run ───────────────────────────────────────────────────

    def run_strategy(self, strategy: str) -> BacktestMetrics:
        """Run one strategy and persist the result to BacktestResult."""
        df = self._load_df()
        horizon_days = HORIZON_DAYS.get(self.horizon, 5)

        if strategy == "sentiment":
            signals = _sentiment_signals(df, self.metal)
        elif strategy in STRATEGY_FN:
            signals = STRATEGY_FN[strategy](df)
        else:
            raise ValueError(f"Unknown strategy: {strategy!r}")

        metrics = _compute_metrics(
            df=df,
            signals=signals,
            horizon_days=horizon_days,
            strategy=strategy,
            metal=self.metal,
            timeframe=self.timeframe,
            horizon=self.horizon,
        )

        # Persist / update in DB
        BacktestResult.objects.update_or_create(
            metal=metrics.metal,
            timeframe=metrics.timeframe,
            strategy=metrics.strategy,
            horizon=metrics.horizon,
            defaults={
                "accuracy": metrics.accuracy,
                "win_rate": metrics.win_rate,
                "total_trades": metrics.total_trades,
                "avg_gain": metrics.avg_gain,
                "avg_loss": metrics.avg_loss,
                "profit_factor": metrics.profit_factor,
                "max_drawdown": metrics.max_drawdown,
                "sharpe_ratio": metrics.sharpe_ratio,
                "total_return": metrics.total_return,
                "start_date": metrics.start_date,
                "end_date": metrics.end_date,
            },
        )

        logger.info(
            "Backtest [%s/%s/%s/%s]: acc=%.1f%% wr=%.1f%% pf=%.2f trades=%d",
            self.metal, self.timeframe, strategy, self.horizon,
            metrics.accuracy, metrics.win_rate, metrics.profit_factor,
            metrics.total_trades,
        )
        return metrics

    # ── Run all strategies ────────────────────────────────────────────────────

    def run_all(self) -> List[BacktestMetrics]:
        """Run all 4 strategies and return a list of BacktestMetrics."""
        results = []
        for strategy in ["rsi", "macd", "composite", "sentiment"]:
            try:
                results.append(self.run_strategy(strategy))
            except Exception as exc:
                logger.warning("Strategy %s failed: %s", strategy, exc)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function (called from Celery tasks)
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(
    metal: str = "gold",
    timeframe: str = "1d",
    horizon: str = "1w",
) -> List[BacktestMetrics]:
    """Entry point for Celery tasks and management commands."""
    engine = BacktestEngine(metal=metal, timeframe=timeframe, horizon=horizon)
    return engine.run_all()


def run_full_backtest_suite() -> dict:
    """
    Run all metal × timeframe × horizon combinations.
    Returns a summary dict keyed by (metal, timeframe, horizon).
    """
    metals = ["gold", "silver"]
    timeframes = ["1d", "1w"]
    horizons = ["1d", "1w", "1mo"]

    summary = {}
    for metal in metals:
        for timeframe in timeframes:
            for horizon in horizons:
                key = f"{metal}/{timeframe}/{horizon}"
                try:
                    results = run_backtest(metal, timeframe, horizon)
                    summary[key] = [
                        {
                            "strategy": r.strategy,
                            "accuracy": r.accuracy,
                            "win_rate": r.win_rate,
                            "profit_factor": r.profit_factor,
                        }
                        for r in results
                    ]
                    logger.info("Completed backtest for %s", key)
                except Exception as exc:
                    summary[key] = {"error": str(exc)}
                    logger.error("Backtest failed for %s: %s", key, exc)

    return summary
