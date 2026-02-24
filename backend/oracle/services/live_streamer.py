"""
Live price streamer: polls spot prices every ~3 seconds,
broadcasts via Django Channels, periodically saves to DB,
and builds 1m/5m OHLCV bars from the live tick stream.

Primary source: GoldAPI (api.gold-api.com) for spot XAU/XAG prices.
Fallback: yfinance fast_info for COMEX futures (GC=F/SI=F).
All network fetches run in parallel via ThreadPoolExecutor.
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
import yfinance as yf
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger('oracle')

# GoldAPI — free, no auth, returns spot prices
GOLDAPI_BASE = 'https://api.gold-api.com/price'
GOLDAPI_SYMBOLS = {
    'gold': 'XAU',
    'silver': 'XAG',
}

# yfinance fallback (COMEX futures — slightly higher than spot)
YF_TICKERS = {
    'gold': 'GC=F',
    'silver': 'SI=F',
}
USDINR_TICKER = 'USDINR=X'
TROY_OZ_PER_GRAM = 31.1035

# MCX India premium over international spot
# (import duty 6% + AIDC 5% + GST 3%, effective ~6.4% for gold, ~2.1% for silver)
MCX_GOLD_PREMIUM = 1.064
MCX_SILVER_PREMIUM = 1.021

GROUP_NAME = 'live_prices'
POLL_INTERVAL = 3           # seconds between broadcast starts (fixed-interval)
DB_SAVE_INTERVAL = 60       # seconds between PriceSnapshot saves
YF_STATS_CACHE_TTL = 60     # 24h stats barely change — cache 60s
USDINR_CACHE_TTL = 30       # USD/INR moves slowly — cache 30s

# Bar intervals to build from ticks (in seconds)
BAR_INTERVALS = {
    '1m': 60,
    '5m': 300,
}


class BarBuilder:
    """Accumulates price ticks into OHLCV bars and flushes completed bars to DB."""

    def __init__(self):
        # {(metal, timeframe): {open, high, low, close, volume, usdinr, bar_start}}
        self._current_bars = {}

    def _bar_start(self, ts: datetime, interval_seconds: int) -> datetime:
        """Round timestamp down to the start of the current bar interval."""
        epoch = int(ts.timestamp())
        aligned = epoch - (epoch % interval_seconds)
        return datetime.fromtimestamp(aligned, tz=timezone.utc)

    def tick(self, metal: str, price: float, usdinr: float, ts: datetime):
        """Ingest a price tick and flush any completed bars."""
        flushed = []

        for tf, interval_secs in BAR_INTERVALS.items():
            key = (metal, tf)
            bar_start = self._bar_start(ts, interval_secs)
            current = self._current_bars.get(key)

            if current and current['bar_start'] < bar_start:
                # This bar is complete — flush it
                flushed.append((metal, tf, current))
                current = None

            if current is None:
                self._current_bars[key] = {
                    'bar_start': bar_start,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'usdinr': usdinr,
                }
            else:
                current['high'] = max(current['high'], price)
                current['low'] = min(current['low'], price)
                current['close'] = price
                current['usdinr'] = usdinr

        if flushed:
            self._save_bars(flushed)

    def _save_bars(self, bars: list):
        """Save completed bars to DB with retry for SQLite locking."""
        from oracle.models import PriceBar

        for metal, tf, bar in bars:
            close_usd = bar['close']
            usdinr = bar['usdinr']
            defaults = {
                'open_usd': round(bar['open'], 4),
                'high_usd': round(bar['high'], 4),
                'low_usd': round(bar['low'], 4),
                'close_usd': round(close_usd, 4),
                'volume': 0,
                'usdinr': round(usdinr, 4),
                'close_inr': round(close_usd * usdinr, 2),
            }
            for attempt in range(3):
                try:
                    PriceBar.objects.update_or_create(
                        metal=metal,
                        timeframe=tf,
                        timestamp=bar['bar_start'],
                        defaults=defaults,
                    )
                    logger.info(f"Bar saved: {metal} {tf} @ {bar['bar_start']:%H:%M} = {close_usd:.2f}")
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(0.5)
                    else:
                        logger.error(f"Bar save failed after retries: {metal} {tf}: {e}")

    def flush_all(self):
        """Force-flush all in-progress bars (e.g. on shutdown)."""
        flushed = []
        for (metal, tf), bar in self._current_bars.items():
            flushed.append((metal, tf, bar))
        self._current_bars.clear()
        if flushed:
            self._save_bars(flushed)


class LiveStreamer:
    def __init__(self):
        self._yf_tickers = {}
        self._last_db_save = 0
        self._bar_builder = BarBuilder()
        self._session = requests.Session()
        self._executor = ThreadPoolExecutor(max_workers=5)
        # Caches: {metal: {value: ..., fetched_at: float}}
        self._spot_cache = {}
        self._yf_stats_cache = {}
        self._usdinr_cache = None

    def _get_yf_ticker(self, symbol: str) -> yf.Ticker:
        if symbol not in self._yf_tickers:
            self._yf_tickers[symbol] = yf.Ticker(symbol)
        return self._yf_tickers[symbol]

    # ── Individual fetchers (run in thread pool) ──────────────────────

    def _fetch_usdinr(self) -> float:
        if self._usdinr_cache and (time.time() - self._usdinr_cache['t']) < USDINR_CACHE_TTL:
            return self._usdinr_cache['v']
        try:
            t = self._get_yf_ticker(USDINR_TICKER)
            info = t.fast_info
            price = getattr(info, 'last_price', None) or getattr(info, 'lastPrice', None)
            if price and price > 0:
                self._usdinr_cache = {'v': float(price), 't': time.time()}
                return float(price)
        except Exception as e:
            logger.warning(f"USDINR failed: {e}")
        return self._usdinr_cache['v'] if self._usdinr_cache else 86.0

    def _fetch_spot_price(self, metal: str) -> float | None:
        """Fetch spot price from GoldAPI. ~180ms per call."""
        symbol = GOLDAPI_SYMBOLS.get(metal)
        if not symbol:
            return None
        try:
            resp = self._session.get(
                f'{GOLDAPI_BASE}/{symbol}', timeout=4,
                headers={'Accept': 'application/json'},
            )
            if resp.status_code == 200:
                price = resp.json().get('price')
                if price and float(price) > 0:
                    self._spot_cache[metal] = {'v': float(price), 't': time.time()}
                    return float(price)
            else:
                logger.warning(f"GoldAPI {symbol}: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"GoldAPI {symbol} failed: {e}")
        # Return stale cache
        cached = self._spot_cache.get(metal)
        return cached['v'] if cached else None

    def _fetch_yf_stats(self, metal: str) -> dict | None:
        """Fetch 24h stats from yfinance. Cached for 60s (barely changes)."""
        cached = self._yf_stats_cache.get(metal)
        if cached and (time.time() - cached['t']) < YF_STATS_CACHE_TTL:
            return cached['v']
        symbol = YF_TICKERS.get(metal)
        if not symbol:
            return None
        try:
            t = self._get_yf_ticker(symbol)
            info = t.fast_info
            lp = getattr(info, 'last_price', None) or getattr(info, 'lastPrice', None)
            if not lp or lp <= 0:
                return cached['v'] if cached else None
            result = {
                'last_price': float(lp),
                'day_high': float(getattr(info, 'day_high', None) or getattr(info, 'dayHigh', None) or lp),
                'day_low': float(getattr(info, 'day_low', None) or getattr(info, 'dayLow', None) or lp),
                'previous_close': float(getattr(info, 'previous_close', None) or getattr(info, 'previousClose', None) or lp),
            }
            self._yf_stats_cache[metal] = {'v': result, 't': time.time()}
            return result
        except Exception as e:
            logger.warning(f"yfinance {symbol} failed: {e}")
            return cached['v'] if cached else None

    # ── Parallel fetch orchestration ──────────────────────────────────

    def _fetch_all_parallel(self) -> dict:
        """Fetch all prices in parallel. Returns {gold_spot, silver_spot, gold_yf, silver_yf, usdinr}."""
        results = {}
        futures = {
            self._executor.submit(self._fetch_spot_price, 'gold'): 'gold_spot',
            self._executor.submit(self._fetch_spot_price, 'silver'): 'silver_spot',
            self._executor.submit(self._fetch_yf_stats, 'gold'): 'gold_yf',
            self._executor.submit(self._fetch_yf_stats, 'silver'): 'silver_yf',
            self._executor.submit(self._fetch_usdinr): 'usdinr',
        }
        for future in as_completed(futures, timeout=6):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.warning(f"Parallel fetch {key} failed: {e}")
                results[key] = None
        return results

    def _build_payload(self) -> dict | None:
        fetched = self._fetch_all_parallel()
        usdinr = fetched.get('usdinr') or (self._usdinr_cache['v'] if self._usdinr_cache else 86.0)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        metals = {}

        for metal in GOLDAPI_SYMBOLS:
            spot_price = fetched.get(f'{metal}_spot')
            yf_stats = fetched.get(f'{metal}_yf')

            if spot_price:
                price_usd = spot_price
                source = 'spot'
            elif yf_stats:
                price_usd = yf_stats['last_price']
                source = 'futures'
            else:
                continue

            day_high = yf_stats['day_high'] if yf_stats else price_usd
            day_low = yf_stats['day_low'] if yf_stats else price_usd
            prev_close = yf_stats['previous_close'] if yf_stats else price_usd

            self._bar_builder.tick(metal, price_usd, usdinr, now)

            change = price_usd - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            price_inr = price_usd * usdinr
            per_gram = price_inr / TROY_OZ_PER_GRAM

            # MCX India price (international spot + import duty/GST premium)
            mcx_premium = MCX_GOLD_PREMIUM if metal == 'gold' else MCX_SILVER_PREMIUM
            mcx_per_gram = per_gram * mcx_premium
            mcx_10g = round(mcx_per_gram * 10) if metal == 'gold' else None
            mcx_kg = round(mcx_per_gram * 1000) if metal == 'silver' else None

            metals[metal] = {
                'price_usd': round(price_usd, 2),
                'high_24h_usd': round(day_high, 2),
                'low_24h_usd': round(day_low, 2),
                'change_24h_usd': round(change, 2),
                'change_24h_pct': round(change_pct, 2),
                'usdinr': round(usdinr, 4),
                'price_inr': round(price_inr, 2),
                'price_per_gram_inr': round(per_gram, 2),
                'price_per_10g_inr': round(per_gram * 10, 2) if metal == 'gold' else None,
                'price_per_kg_inr': round(per_gram * 1000, 2) if metal == 'silver' else None,
                'mcx_price_10g': mcx_10g,
                'mcx_price_kg': mcx_kg,
                'mcx_price_per_gram': round(mcx_per_gram, 2),
                'updated_at': now_iso,
                'source': source,
            }

        if not metals:
            return None
        return {'type': 'price_update', 'timestamp': now_iso, 'metals': metals}

    def _save_to_db(self, payload: dict):
        from oracle.models import PriceSnapshot

        for metal, data in payload.get('metals', {}).items():
            try:
                PriceSnapshot.objects.update_or_create(
                    metal=metal,
                    defaults={
                        'price_usd': data['price_usd'],
                        'high_24h_usd': data['high_24h_usd'],
                        'low_24h_usd': data['low_24h_usd'],
                        'change_24h_usd': data['change_24h_usd'],
                        'change_24h_pct': data['change_24h_pct'],
                        'usdinr': data['usdinr'],
                        'price_inr': data['price_inr'],
                        'price_per_gram_inr': data['price_per_gram_inr'],
                        'price_per_10g_inr': data.get('price_per_10g_inr'),
                        'price_per_kg_inr': data.get('price_per_kg_inr'),
                        'mcx_price_per_gram': data.get('mcx_price_per_gram'),
                        'mcx_price_10g': data.get('mcx_price_10g'),
                        'mcx_price_kg': data.get('mcx_price_kg'),
                    },
                )
            except Exception as e:
                logger.error(f"DB save failed for {metal}: {e}")

    def run(self):
        logger.info(
            "LiveStreamer starting — parallel fetch, spot via GoldAPI (fallback: yfinance), "
            "broadcast every %ds, yf_stats cached %ds, DB save every %ds, bars: %s",
            POLL_INTERVAL, YF_STATS_CACHE_TTL, DB_SAVE_INTERVAL, list(BAR_INTERVALS.keys()),
        )
        channel_layer = get_channel_layer()
        group_send = async_to_sync(channel_layer.group_send)

        while True:
            cycle_start = time.monotonic()
            try:
                payload = self._build_payload()
                if payload:
                    group_send(GROUP_NAME, {
                        'type': 'price_update',
                        'data': payload,
                    })

                    now = time.time()
                    if now - self._last_db_save >= DB_SAVE_INTERVAL:
                        self._save_to_db(payload)
                        self._last_db_save = now
                        logger.info("Saved prices to DB")

            except Exception as e:
                logger.error(f"Streamer loop error: {e}", exc_info=True)

            # Fixed-interval: sleep only the remaining time to hit exact POLL_INTERVAL
            elapsed = time.monotonic() - cycle_start
            sleep_for = max(0.1, POLL_INTERVAL - elapsed)
            time.sleep(sleep_for)
