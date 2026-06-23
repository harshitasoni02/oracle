# backend/oracle/urls_backtest.py
"""
Backtesting URL patterns.

Include in your main urls.py:

    from oracle.urls_backtest import urlpatterns as backtest_urls
    urlpatterns += backtest_urls

  OR use include():

    path("api/backtesting/", include("oracle.urls_backtest")),
"""

from django.urls import path

from oracle.views_backtest import (
    BacktestResultListView,
    BacktestSummaryView,
    PredictionVerificationListView,
    TriggerBacktestView,
    TriggerVerificationView,
    VerificationStatsView,
)

urlpatterns = [
    # GET  – all raw BacktestResult rows
    path(
        "api/backtesting/",
        BacktestResultListView.as_view(),
        name="backtesting-list",
    ),
    # GET  – aggregated best-strategy summary per timeframe
    path(
        "api/backtesting/summary/",
        BacktestSummaryView.as_view(),
        name="backtesting-summary",
    ),
    # GET  – paginated list of individual PredictionVerification records
    path(
        "api/backtesting/history/",
        PredictionVerificationListView.as_view(),
        name="backtesting-history",
    ),
    # GET  – aggregate MAE / RMSE / MAPE stats
    path(
        "api/backtesting/verification/",
        VerificationStatsView.as_view(),
        name="backtesting-verification-stats",
    ),
    # POST – trigger a backtest run
    path(
        "api/backtesting/run/",
        TriggerBacktestView.as_view(),
        name="backtesting-run",
    ),
    # POST – trigger prediction verification
    path(
        "api/backtesting/verify/",
        TriggerVerificationView.as_view(),
        name="backtesting-verify",
    ),
]
