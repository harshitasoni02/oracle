"""
Data fetcher: downloads OHLCV data and USD/INR rates,
converts to INR, and persists to the database.

Spot prices from GoldAPI (api.gold-api.com) with yfinance futures fallback.
Historical bars from yfinance (COMEX futures).
"""
import logging
from datetime import timezone

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger('oracle')

# GoldAPI — spot prices (primary for current price)
GOLDAPI_BASE = 'https://api.gold-api.com/price'
GOLDAPI_SYMBOLS = {
    'gold': 'XAU',
    'silver': 'XAG',
}

# yfinance — COMEX futures (for historical bars + fallback)
METAL_TICKERS = {
    'gold': 'GC=F',
    'silver': 'SI=F',
}
USDINR_TICKER = 'USDINR=X'
DJI_TICKER = '^DJI'

TROY_OZ_PER_GRAM = 31.1035
TROY_OZ_PER_KG = 32150.7

# MCX India premium over international spot
MCX_GOLD_PREMIUM = 1.064
MCX_SILVER_PREMIUM = 1.021

TIMEFRAME_FETCH_CONFIG = {
    '1m':  {'period': '7d',   'interval': '1m'},
    '5m':  {'period': '60d',  'interval': '5m'},
    '15m': {'period': '5d',   'interval': '15m'},
    '1h':  {'period': '60d',  'interval': '1h'},
    '1d':  {'period': '2y',   'interval': '1d'},
    '1w':  {'period': '10y',  'interval': '1wk'},
}


def _scalar(series_or_val) -> float:
    """Convert a potentially Series-valued yfinance cell to a plain float.

    Newer yfinance (>=0.2.38) may return MultiIndex DataFrames even for
    single-ticker downloads, so df['Close'].iloc[-1] is a 1-element Series
    instead of a scalar.  .squeeze() + float() handles both cases.
    """
    import numpy as np
    if isinstance(series_or_val, (pd.Series, pd.DataFrame)):
        v = series_or_val.squeeze()
        if isinstance(v, (pd.Series, pd.DataFrame)):
            v = v.iloc[0]
        return float(v)
    return float(series_or_val)


def _close_series(df: pd.DataFrame, ticker: str | None = None) -> pd.Series:
    """Return a plain 1-D Close series regardless of MultiIndex columns."""
    col = df['Close']
    if isinstance(col, pd.DataFrame):
        # MultiIndex: columns are (field, ticker)
        if ticker and ticker in col.columns:
            return col[ticker]
        return col.iloc[:, 0]
    return col


def _get_usdinr_fast() -> float | None:
    """Try fetching USD/INR via fast_info (real-time quoted price)."""
    try:
        t = yf.Ticker(USDINR_TICKER)
        info = t.fast_info
        price = getattr(info, 'last_price', None) or getattr(info, 'lastPrice', None)
        if price and price > 0:
            return float(price)
    except Exception as e:
        logger.warning(f"fast_info USDINR failed: {e}")
    return None


def _get_usdinr() -> float:
    """Fetch current USD/INR exchange rate. Tries fast_info first, falls back to download."""
    fast = _get_usdinr_fast()
    if fast:
        return fast
    try:
        hist = yf.download(USDINR_TICKER, period='5d', interval='1d', progress=False, auto_adjust=True)
        if not hist.empty:
            return _scalar(_close_series(hist, USDINR_TICKER).iloc[-1])
    except Exception as e:
        logger.warning(f"Could not fetch USD/INR: {e}")
    return 86.0


def fetch_dji_dataframe(limit: int = 500) -> 'pd.DataFrame':
    """Fetch DJI daily bars for correlation analysis. Returns a DataFrame with OHLCV columns."""
    try:
        raw = yf.download(DJI_TICKER, period='2y', interval='1d', progress=False, auto_adjust=True)
        if raw.empty:
            logger.warning("No DJI data returned")
            return pd.DataFrame()

        # Handle MultiIndex (yfinance >= 0.2.38 may produce it even for single ticker)
        if isinstance(raw.columns, pd.MultiIndex):
            try:
                df = raw.xs(DJI_TICKER, level=1, axis=1)
            except KeyError:
                df = raw.xs(raw.columns.get_level_values(1)[0], level=1, axis=1)
        else:
            df = raw

        df = df.dropna(subset=['Close'])
        if len(df) > limit:
            df = df.iloc[-limit:]
        logger.info(f"DJI: fetched {len(df)} daily bars")
        return df
    except Exception as e:
        logger.warning(f"Could not fetch DJI data: {e}")
        return pd.DataFrame()


def _fetch_spot_price_api(metal: str) -> float | None:
    """Fetch spot price from GoldAPI. Returns price in USD or None."""
    symbol = GOLDAPI_SYMBOLS.get(metal)
    if not symbol:
        return None
    try:
        resp = requests.get(
            f'{GOLDAPI_BASE}/{symbol}',
            timeout=10,
            headers={'Accept': 'application/json'},
        )
        if resp.status_code == 200:
            j = resp.json()
            price = j.get('price')
            if price and float(price) > 0:
                return float(price)
        logger.warning(f"GoldAPI {symbol}: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"GoldAPI {symbol} failed: {e}")
    return None


def _fetch_yf_stats(metal: str) -> dict | None:
    """Fetch price + 24h stats from yfinance fast_info (futures)."""
    ticker_sym = METAL_TICKERS.get(metal)
    if not ticker_sym:
        return None
    try:
        t = yf.Ticker(ticker_sym)
        info = t.fast_info
        current = getattr(info, 'last_price', None) or getattr(info, 'lastPrice', None)
        if not current or current <= 0:
            return None
        day_high = getattr(info, 'day_high', None) or getattr(info, 'dayHigh', None) or current
        day_low = getattr(info, 'day_low', None) or getattr(info, 'dayLow', None) or current
        prev = getattr(info, 'previous_close', None) or getattr(info, 'previousClose', None) or current
        return {
            'last_price': float(current),
            'day_high': float(day_high),
            'day_low': float(day_low),
            'previous_close': float(prev),
        }
    except Exception as e:
        logger.warning(f"yfinance fast_info {ticker_sym} failed: {e}")
    return None


def fetch_and_save_current_prices():
    """Fetch current spot prices and save/update PriceSnapshot for gold and silver."""
    from oracle.models import PriceSnapshot

    usdinr = _get_usdinr()
    logger.info(f"USD/INR: {usdinr:.4f}")

    for metal in GOLDAPI_SYMBOLS:
        try:
            # Get spot price from GoldAPI (accurate)
            spot_price = _fetch_spot_price_api(metal)
            # Get 24h stats from yfinance (high/low/prev_close from futures)
            yf_stats = _fetch_yf_stats(metal)

            if spot_price:
                current = spot_price
                source = 'spot'
            elif yf_stats:
                current = yf_stats['last_price']
                source = 'futures'
            else:
                logger.warning(f"No price data for {metal} from any source")
                continue

            day_high = yf_stats['day_high'] if yf_stats else current
            day_low = yf_stats['day_low'] if yf_stats else current
            prev = yf_stats['previous_close'] if yf_stats else current

            change = current - prev
            change_pct = (change / prev * 100) if prev else 0

            price_inr = current * usdinr
            per_gram = price_inr / TROY_OZ_PER_GRAM

            mcx_premium = MCX_GOLD_PREMIUM if metal == 'gold' else MCX_SILVER_PREMIUM
            mcx_per_gram = per_gram * mcx_premium

            PriceSnapshot.objects.update_or_create(
                metal=metal,
                defaults={
                    'price_usd': round(current, 2),
                    'high_24h_usd': round(day_high, 2),
                    'low_24h_usd': round(day_low, 2),
                    'change_24h_usd': round(change, 2),
                    'change_24h_pct': round(change_pct, 2),
                    'usdinr': round(usdinr, 4),
                    'price_inr': round(price_inr, 2),
                    'price_per_gram_inr': round(per_gram, 2),
                    'price_per_10g_inr': round(per_gram * 10, 2) if metal == 'gold' else None,
                    'price_per_kg_inr': round(per_gram * 1000, 2) if metal == 'silver' else None,
                    'mcx_price_10g': round(mcx_per_gram * 10) if metal == 'gold' else None,
                    'mcx_price_kg': round(mcx_per_gram * 1000) if metal == 'silver' else None,
                    'mcx_price_per_gram': round(mcx_per_gram, 2),
                }
            )
            logger.info(f"Updated {metal} ({source}): ${current:.2f} / ₹{per_gram:.0f}/g")

        except Exception as e:
            logger.error(f"Failed to fetch {metal}: {e}")


def fetch_and_save_bars(metal: str, timeframe: str):
    """Download OHLCV bars for a specific metal+timeframe and upsert into PriceBar."""
    from oracle.models import PriceBar

    ticker_sym = METAL_TICKERS.get(metal)
    config = TIMEFRAME_FETCH_CONFIG.get(timeframe)
    if not ticker_sym or not config:
        return

    logger.info(f"Fetching {metal} {timeframe} bars ({config['period']}/{config['interval']})")

    try:
        # Download metal + USDINR together
        symbols = [ticker_sym, USDINR_TICKER]
        raw = yf.download(
            symbols,
            period=config['period'],
            interval=config['interval'],
            progress=False,
            auto_adjust=True,
        )

        if raw.empty:
            logger.warning(f"No data returned for {metal} {timeframe}")
            return

        # Handle single vs multi-ticker response
        if isinstance(raw.columns, pd.MultiIndex):
            metal_df = raw.xs(ticker_sym, level=1, axis=1)
            try:
                usdinr_series = raw.xs(USDINR_TICKER, level=1, axis=1)['Close']
            except Exception:
                usdinr_series = pd.Series(86.0, index=raw.index)
        else:
            metal_df = raw
            usdinr_series = pd.Series(86.0, index=raw.index)

        usdinr_series = usdinr_series.ffill().fillna(86.0)

        bars_to_create = []
        bars_to_update = []

        existing = {
            b.timestamp: b
            for b in PriceBar.objects.filter(metal=metal, timeframe=timeframe)
        }

        for idx, row in metal_df.iterrows():
            if pd.isna(row.get('Close')):
                continue

            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            usdinr_val = float(usdinr_series.get(idx, 86.0))
            close_usd = float(row['Close'])

            data = {
                'open_usd': round(float(row.get('Open', close_usd)), 4),
                'high_usd': round(float(row.get('High', close_usd)), 4),
                'low_usd': round(float(row.get('Low', close_usd)), 4),
                'close_usd': round(close_usd, 4),
                'volume': round(float(row.get('Volume', 0) or 0), 2),
                'usdinr': round(usdinr_val, 4),
                'close_inr': round(close_usd * usdinr_val, 2),
            }

            if ts in existing:
                bar = existing[ts]
                for k, v in data.items():
                    setattr(bar, k, v)
                bars_to_update.append(bar)
            else:
                bars_to_create.append(PriceBar(metal=metal, timeframe=timeframe, timestamp=ts, **data))

        if bars_to_create:
            PriceBar.objects.bulk_create(bars_to_create, ignore_conflicts=True)
        if bars_to_update:
            PriceBar.objects.bulk_update(
                bars_to_update,
                ['open_usd', 'high_usd', 'low_usd', 'close_usd', 'volume', 'usdinr', 'close_inr'],
            )

        logger.info(f"{metal} {timeframe}: created {len(bars_to_create)}, updated {len(bars_to_update)}")

    except Exception as e:
        logger.error(f"Failed to fetch bars for {metal} {timeframe}: {e}", exc_info=True)


def get_bars_as_dataframe(metal: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """Return PriceBar rows as a DataFrame for indicator computation."""
    from oracle.models import PriceBar

    qs = (
        PriceBar.objects
        .filter(metal=metal, timeframe=timeframe)
        .order_by('-timestamp')[:limit]
        .values('timestamp', 'open_usd', 'high_usd', 'low_usd', 'close_usd', 'volume')
    )
    rows = list(qs)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows[::-1])  # oldest first
    df = df.rename(columns={
        'open_usd': 'Open',
        'high_usd': 'High',
        'low_usd': 'Low',
        'close_usd': 'Close',
        'volume': 'Volume',
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.set_index('timestamp')
    return df
