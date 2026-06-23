# backend/oracle/tasks_backtest.py
"""
Celery tasks for the backtesting engine.
Add these to your existing tasks.py or import them from there.

In your celery.py beat schedule, add:
    "run-backtest-daily": {
        "task": "oracle.tasks_backtest.run_backtest_task",
        "schedule": crontab(hour=1, minute=0),   # 01:00 UTC every day
    },
    "verify-predictions-daily": {
        "task": "oracle.tasks_backtest.verify_predictions_task",
        "schedule": crontab(hour=2, minute=0),   # 02:00 UTC every day
    },
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def run_backtest_task(self, metal: str = None, timeframe: str = None, horizon: str = None):
    """
    Run backtest for a specific combination, or the full suite if no args given.
    """
    from oracle.services.backtesting import run_backtest, run_full_backtest_suite

    try:
        if metal and timeframe and horizon:
            results = run_backtest(metal=metal, timeframe=timeframe, horizon=horizon)
            return {
                "status": "ok",
                "results": [
                    {
                        "strategy": r.strategy,
                        "accuracy": r.accuracy,
                        "win_rate": r.win_rate,
                        "profit_factor": r.profit_factor,
                        "total_trades": r.total_trades,
                    }
                    for r in results
                ],
            }
        else:
            summary = run_full_backtest_suite()
            return {"status": "ok", "combinations": len(summary)}
    except Exception as exc:
        logger.exception("Backtest task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def verify_predictions_task(self, metal: str = None, timeframe: str = None):
    """
    Verify predictions for a specific combination, or all if no args given.
    """
    from oracle.services.prediction_verification import (
        run_full_verification,
        verify_predictions,
    )

    try:
        if metal and timeframe:
            stats = verify_predictions(metal=metal, timeframe=timeframe)
            return {
                "status": "ok",
                "total_verified": stats.total_verified,
                "mae": stats.mae,
                "mape": stats.mape,
                "directional_accuracy": stats.directional_accuracy,
            }
        else:
            results = run_full_verification()
            return {
                "status": "ok",
                "combinations_verified": len(results),
                "summary": {
                    k: {
                        "total": v.total_verified,
                        "mape": v.mape,
                        "da": v.directional_accuracy,
                    }
                    for k, v in results.items()
                },
            }
    except Exception as exc:
        logger.exception("Verification task failed: %s", exc)
        raise self.retry(exc=exc)
