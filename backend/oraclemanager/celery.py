import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oraclemanager.settings')

app = Celery('oraclemanager')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Refresh current prices every 5 minutes
    'refresh-prices-5min': {
        'task': 'oracle.tasks.refresh_prices',
        'schedule': 300,
    },
    # Refresh 1m/5m bars every 5 minutes
    'refresh-minute-bars-5min': {
        'task': 'oracle.tasks.refresh_minute_bars',
        'schedule': 300,
    },
    # Refresh 15m/1h bars every 15 minutes
    'refresh-intraday-15min': {
        'task': 'oracle.tasks.refresh_intraday_bars',
        'schedule': 900,
    },
    # Refresh daily/weekly bars every hour
    'refresh-historical-hourly': {
        'task': 'oracle.tasks.refresh_historical_bars',
        'schedule': crontab(minute=5),
    },
    # Recompute indicators every 15 minutes
    'compute-indicators-15min': {
        'task': 'oracle.tasks.compute_all_indicators',
        'schedule': 900,
    },
    # Generate predictions every 30 minutes
    'generate-predictions-30min': {
        'task': 'oracle.tasks.generate_all_predictions',
        'schedule': 1800,
    },
    # Refresh news sentiment every 3 hours
    'refresh-sentiment-3h': {
        'task': 'oracle.tasks.refresh_sentiment',
        'schedule': 3 * 60 * 60,  # 10800 seconds
    },
    # Run backtest daily at 01:00 UTC
    'run-backtest-daily': {
        'task': 'oracle.tasks_backtest.run_backtest_task',
        'schedule': crontab(hour=1, minute=0),
    },
    # Verify scheduled predictions every minute (1d and 1w only)
    'verify-scheduled-predictions': {
        'task': 'oracle.tasks_backtest.verify_scheduled_predictions',
        'schedule': 60,
    },
    # Verify predictions daily at 02:00 UTC (manual trigger fallback)
    'verify-predictions-daily': {
        'task': 'oracle.tasks_backtest.verify_predictions_task',
        'schedule': crontab(hour=2, minute=0),
    },
}
