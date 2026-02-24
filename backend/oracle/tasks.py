import logging
from celery import shared_task

logger = logging.getLogger('oracle')

METALS = ['gold', 'silver']
ALL_TIMEFRAMES = ['1m', '5m', '15m', '1h', '1d', '1wk']


@shared_task(name='oracle.tasks.refresh_prices')
def refresh_prices():
    from oracle.services.data_fetcher import fetch_and_save_current_prices
    logger.info("Refreshing current prices...")
    fetch_and_save_current_prices()


@shared_task(name='oracle.tasks.refresh_minute_bars')
def refresh_minute_bars():
    """Refresh 1m and 5m bars — tries Twelve Data first, falls back to yfinance.

    Note: The live streamer also builds 1m/5m bars from ticks in real-time.
    This task serves as a backfill / gap-filler for historical data.
    """
    from oracle.services.twelvedata_fetcher import fetch_bars_twelvedata
    from oracle.services.data_fetcher import fetch_and_save_bars
    for metal in METALS:
        for tf in ['1m', '5m']:
            if not fetch_bars_twelvedata(metal, tf):
                logger.info(f"Twelve Data unavailable for {metal} {tf}, falling back to yfinance")
                fetch_and_save_bars(metal, tf)


@shared_task(name='oracle.tasks.refresh_intraday_bars')
def refresh_intraday_bars():
    from oracle.services.data_fetcher import fetch_and_save_bars
    for metal in METALS:
        for tf in ['15m', '1h']:
            fetch_and_save_bars(metal, tf)


@shared_task(name='oracle.tasks.refresh_historical_bars')
def refresh_historical_bars():
    from oracle.services.data_fetcher import fetch_and_save_bars
    for metal in METALS:
        for tf in ['1d', '1wk']:
            fetch_and_save_bars(metal, tf)


@shared_task(name='oracle.tasks.compute_all_indicators')
def compute_all_indicators():
    from oracle.services.data_fetcher import get_bars_as_dataframe, fetch_dji_dataframe
    from oracle.services.indicators import compute_indicators
    from oracle.models import IndicatorSnapshot, SentimentSnapshot

    # Fetch DJI once — shared across all metals/timeframes
    dji_df = fetch_dji_dataframe()

    for metal in METALS:
        # Load sentiment snapshot once per metal (same snapshot applies to all timeframes)
        try:
            sent_snap = SentimentSnapshot.objects.get(metal=metal)
        except SentimentSnapshot.DoesNotExist:
            sent_snap = None

        for tf in ALL_TIMEFRAMES:
            df = get_bars_as_dataframe(metal, tf, limit=500)
            if df.empty:
                logger.info(f"No bars for {metal} {tf}, skipping indicators")
                continue

            vals = compute_indicators(df, dji_df=dji_df, sentiment_snapshot=sent_snap)
            if not vals:
                continue

            IndicatorSnapshot.objects.update_or_create(
                metal=metal,
                timeframe=tf,
                defaults=vals,
            )
            logger.info(f"Indicators {metal} {tf}: {vals.get('signal_label')} ({vals.get('signal_score', 0):+.2f})")


@shared_task(name='oracle.tasks.generate_all_predictions')
def generate_all_predictions():
    from oracle.services.prediction import generate_predictions
    for metal in METALS:
        generate_predictions(metal)


@shared_task(name='oracle.tasks.refresh_sentiment')
def refresh_sentiment():
    """Fetch news RSS feeds, score with FinBERT, broadcast sentiment snapshot via WebSocket."""
    from oracle.services.news_fetcher import fetch_all_news, save_and_score_articles
    from oracle.services.sentiment import score_text, compute_sentiment_snapshot
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    channel_layer = get_channel_layer()

    for metal in METALS:
        logger.info(f"Refreshing sentiment for {metal}...")
        articles = fetch_all_news(metal)
        new_count = save_and_score_articles(articles, metal, score_text)
        logger.info(f"Sentiment {metal}: {new_count} new articles scored")

        # Always recompute rolling windows (decay changes over time even without new articles)
        snapshot = compute_sentiment_snapshot(metal)

        # Push via existing WebSocket channel group (same as LiveStreamer uses)
        if channel_layer:
            async_to_sync(channel_layer.group_send)('live_prices', {
                'type': 'sentiment_update',
                'data': {
                    'type': 'sentiment_update',
                    'metal': metal,
                    **snapshot,
                },
            })


@shared_task(name='oracle.tasks.refresh_all')
def refresh_all():
    """Full sequential refresh: prices -> bars -> sentiment -> indicators -> predictions.
    Sentiment runs before indicators so the composite signal includes news weight.
    """
    from oracle.services.data_fetcher import fetch_and_save_current_prices, fetch_and_save_bars, get_bars_as_dataframe, fetch_dji_dataframe
    from oracle.services.indicators import compute_indicators
    from oracle.services.prediction import generate_predictions
    from oracle.models import IndicatorSnapshot, SentimentSnapshot

    logger.info("=== Full refresh starting ===")

    # 1. Current prices
    fetch_and_save_current_prices()

    # 2. All price bars
    for metal in METALS:
        for tf in ALL_TIMEFRAMES:
            fetch_and_save_bars(metal, tf)

    # 3. News sentiment (before indicators — feeds into composite signal)
    refresh_sentiment()

    # 4. DJI data (fetched once, shared across timeframes)
    dji_df = fetch_dji_dataframe()

    # 5. Indicators (now has fresh sentiment snapshots)
    for metal in METALS:
        try:
            sent_snap = SentimentSnapshot.objects.get(metal=metal)
        except SentimentSnapshot.DoesNotExist:
            sent_snap = None

        for tf in ALL_TIMEFRAMES:
            df = get_bars_as_dataframe(metal, tf, limit=500)
            if df.empty:
                continue
            vals = compute_indicators(df, dji_df=dji_df, sentiment_snapshot=sent_snap)
            if vals:
                IndicatorSnapshot.objects.update_or_create(metal=metal, timeframe=tf, defaults=vals)

    # 6. Predictions (uses updated IndicatorSnapshot which now includes sentiment)
    for metal in METALS:
        generate_predictions(metal)

    logger.info("=== Full refresh complete ===")
