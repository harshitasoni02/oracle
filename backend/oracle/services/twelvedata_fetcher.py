"""
Twelve Data fetcher: downloads fine-grained OHLCV candles (1m, 5m) for gold and silver.
Uses the Twelve Data API (free tier: 800 credits/day, 8 calls/min).
Falls back to yfinance if API key is not configured or quota is exhausted.
"""
import logging
from datetime import timezone

import pandas as pd
from django.conf import settings

logger = logging.getLogger('oracle')

# Twelve Data symbols for precious metals (spot prices)
TD_METAL_SYMBOLS = {
    'gold': 'XAU/USD',
    'silver': 'XAG/USD',
}

TD_USDINR_SYMBOL = 'USD/INR'

# Map our timeframe keys to Twelve Data interval strings
TD_INTERVAL_MAP = {
    '1m': '1min',
    '5m': '5min',
    '15m': '15min',
    '1h': '1h',
    '1d': '1day',
    '1w': '1week',
}

# How many bars to fetch per call (covers enough history for each timeframe)
TD_OUTPUTSIZE = {
    '1m': 500,     # ~8 hours of 1m bars
    '5m': 500,     # ~42 hours of 5m bars
    '15m': 400,    # ~4 days
    '1h': 300,     # ~12 days
    '1d': 500,     # ~2 years
    '1w': 260,    # ~5 years
}


def _get_td_client():
    """Get a Twelve Data client, or None if API key is not configured."""
    api_key = getattr(settings, 'TWELVEDATA_API_KEY', '')
    if not api_key:
        return None
    try:
        from twelvedata import TDClient
        return TDClient(apikey=api_key)
    except ImportError:
        logger.warning("twelvedata package not installed")
        return None


def _fetch_usdinr_td(td_client) -> float:
    """Fetch USD/INR rate from Twelve Data."""
    try:
        data = td_client.price(symbol=TD_USDINR_SYMBOL).as_json()
        price = float(data.get('price', 0))
        if price > 0:
            return price
    except Exception as e:
        logger.warning(f"Twelve Data USD/INR failed: {e}")
    return 0


def fetch_bars_twelvedata(metal: str, timeframe: str) -> bool:
    """Fetch OHLCV bars from Twelve Data and save to PriceBar.

    Returns True if successful, False if failed (caller should fall back to yfinance).
    """
    from oracle.models import PriceBar

    td_client = _get_td_client()
    if not td_client:
        return False

    symbol = TD_METAL_SYMBOLS.get(metal)
    interval = TD_INTERVAL_MAP.get(timeframe)
    if not symbol or not interval:
        return False

    outputsize = TD_OUTPUTSIZE.get(timeframe, 500)

    logger.info(f"[TwelveData] Fetching {metal} {timeframe} ({symbol} @ {interval}, outputsize={outputsize})")

    try:
        ts = td_client.time_series(
            symbol=symbol,
            interval=interval,
            outputsize=outputsize,
            timezone='UTC',
        )
        df = ts.as_pandas()

        if df is None or df.empty:
            logger.warning(f"[TwelveData] No data for {metal} {timeframe}")
            return False

        # Twelve Data returns newest-first; reverse to oldest-first
        df = df.sort_index()

        # Fetch USD/INR for conversion
        usdinr = _fetch_usdinr_td(td_client)
        if usdinr <= 0:
            # Fall back to yfinance for USDINR
            from oracle.services.data_fetcher import _get_usdinr
            usdinr = _get_usdinr()

        # Upsert bars
        existing = {
            b.timestamp: b
            for b in PriceBar.objects.filter(metal=metal, timeframe=timeframe)
        }

        bars_to_create = []
        bars_to_update = []

        for idx, row in df.iterrows():
            close_val = row.get('close')
            if pd.isna(close_val):
                continue

            ts_dt = idx.to_pydatetime()
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)

            close_usd = float(close_val)
            data = {
                'open_usd': round(float(row.get('open', close_usd)), 4),
                'high_usd': round(float(row.get('high', close_usd)), 4),
                'low_usd': round(float(row.get('low', close_usd)), 4),
                'close_usd': round(close_usd, 4),
                'volume': round(float(row.get('volume', 0) or 0), 2),
                'usdinr': round(usdinr, 4),
                'close_inr': round(close_usd * usdinr, 2),
            }

            if ts_dt in existing:
                bar = existing[ts_dt]
                for k, v in data.items():
                    setattr(bar, k, v)
                bars_to_update.append(bar)
            else:
                bars_to_create.append(
                    PriceBar(metal=metal, timeframe=timeframe, timestamp=ts_dt, **data)
                )

        if bars_to_create:
            PriceBar.objects.bulk_create(bars_to_create, ignore_conflicts=True)
        if bars_to_update:
            PriceBar.objects.bulk_update(
                bars_to_update,
                ['open_usd', 'high_usd', 'low_usd', 'close_usd', 'volume', 'usdinr', 'close_inr'],
            )

        logger.info(f"[TwelveData] {metal} {timeframe}: created {len(bars_to_create)}, updated {len(bars_to_update)}")
        return True

    except Exception as e:
        logger.error(f"[TwelveData] Failed {metal} {timeframe}: {e}", exc_info=True)
        return False
