# backend/oracle/views_backtest.py
"""
API Views for the Backtesting Engine.

Endpoints
─────────
GET  /api/backtesting/                 All BacktestResult rows (filterable)
GET  /api/backtesting/summary/         Aggregated best-strategy view
GET  /api/backtesting/history/         PredictionVerification list (paginated)
GET  /api/backtesting/verification/    Aggregate MAE/RMSE/MAPE stats
POST /api/backtesting/run/             Trigger a backtest run (async via Celery)
POST /api/backtesting/verify/          Trigger prediction verification (async)
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from oracle.models import BacktestResult, PredictionVerification
from oracle.serializers_backtest import (
    BacktestResultSerializer,
    BacktestSummarySerializer,
    PredictionVerificationSerializer,
    TriggerBacktestSerializer,
    VerificationStatsSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/backtesting/
# ─────────────────────────────────────────────────────────────────────────────

class BacktestResultListView(APIView):
    """
    Returns all BacktestResult rows.
    Supports optional query params: ?metal=gold&timeframe=1d&strategy=rsi
    """

    def get(self, request):
        qs = BacktestResult.objects.exclude(strategy="sentiment")

        metal = request.query_params.get("metal")
        timeframe = request.query_params.get("timeframe")
        strategy = request.query_params.get("strategy")
        horizon = request.query_params.get("horizon")

        if metal:
            qs = qs.filter(metal=metal)
        if timeframe:
            qs = qs.filter(timeframe=timeframe)
        if strategy:
            qs = qs.filter(strategy=strategy)
        if horizon:
            qs = qs.filter(horizon=horizon)

        serializer = BacktestResultSerializer(qs, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/backtesting/summary/
# ─────────────────────────────────────────────────────────────────────────────

class BacktestSummaryView(APIView):
    """
    For each (metal, timeframe, horizon) combination, returns:
    - best strategy by accuracy
    - best strategy by profit factor
    - all strategy results grouped together
    """

    def get(self, request):
        metal = request.query_params.get("metal", "gold")
        horizon = request.query_params.get("horizon", "1w")

        summaries = []
        timeframes = ["1d", "1w", "1mo"]

        for tf in timeframes:
            results = BacktestResult.objects.filter(
                metal=metal, timeframe=tf, horizon=horizon
            ).exclude(strategy="sentiment")
            if not results.exists():
                continue

            best_accuracy = max(results, key=lambda r: r.accuracy)
            best_pf = max(results, key=lambda r: r.profit_factor)

            summaries.append({
                "metal": metal,
                "timeframe": tf,
                "best_strategy": best_accuracy.strategy,
                "best_accuracy": best_accuracy.accuracy,
                "best_profit_factor": best_pf.profit_factor,
                "total_runs": results.count(),
                "strategies": BacktestResultSerializer(results, many=True).data,
            })

        return Response(summaries)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/backtesting/history/
# ─────────────────────────────────────────────────────────────────────────────

class PredictionVerificationListView(APIView):
    """
    Paginated list of individual PredictionVerification records.
    Supports: ?metal=gold&timeframe=1d&page=1&page_size=50
    Only returns 1d and 1w verifications.
    """

    def get(self, request):
        metal = request.query_params.get("metal")
        timeframe = request.query_params.get("timeframe")
        direction_filter = request.query_params.get("direction_correct")

        qs = PredictionVerification.objects.filter(
            timeframe__in=["1d", "1w"]
        )

        if metal:
            qs = qs.filter(metal=metal)
        if timeframe and timeframe in ("1d", "1w"):
            qs = qs.filter(timeframe=timeframe)
        if direction_filter is not None:
            qs = qs.filter(direction_correct=direction_filter.lower() == "true")

        # Simple manual pagination
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 50)), 200)
        except ValueError:
            page, page_size = 1, 50

        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()
        page_qs = qs[start:end]

        serializer = PredictionVerificationSerializer(page_qs, many=True)
        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": serializer.data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/backtesting/verification/
# ─────────────────────────────────────────────────────────────────────────────

class VerificationStatsView(APIView):
    """
    Returns aggregate MAE, RMSE, MAPE, Directional Accuracy.
    Supports: ?metal=gold&timeframe=1d
    Only includes 1d and 1w verifications.
    When timeframe is omitted, aggregates across both 1d and 1w.
    """

    def get(self, request):
        from oracle.services.prediction_verification import compute_verification_stats

        metal = request.query_params.get("metal", "gold")
        timeframe = request.query_params.get("timeframe")

        # Only allow 1d and 1w
        if timeframe and timeframe not in ("1d", "1w"):
            return Response(
                {"error": "timeframe must be '1d' or '1w'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timeframe:
            stats = compute_verification_stats(metal=metal, timeframe=timeframe)
        else:
            # Aggregate across both 1d and 1w
            stats = compute_verification_stats(metal=metal, timeframe=None)
        serializer = VerificationStatsSerializer(stats.__dict__)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/backtesting/run/
# ─────────────────────────────────────────────────────────────────────────────

class TriggerBacktestView(APIView):
    """
    Triggers a backtest run.

    Body (JSON):
        { "metal": "gold", "timeframe": "1d", "horizon": "1w" }

    Runs synchronously if Celery is unavailable, async otherwise.
    """

    def post(self, request):
        ser = TriggerBacktestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        metal = ser.validated_data["metal"]
        timeframe = ser.validated_data["timeframe"]
        horizon = ser.validated_data["horizon"]

        try:
            from oracle.tasks_backtest import run_backtest_task
            task = run_backtest_task.delay(
                metal=metal, timeframe=timeframe, horizon=horizon
            )
            return Response(
                {"status": "queued", "task_id": task.id},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception:
            # Celery not available — run synchronously
            from oracle.services.backtesting import run_backtest
            results = run_backtest(metal=metal, timeframe=timeframe, horizon=horizon)
            return Response(
                {
                    "status": "completed",
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
                },
                status=status.HTTP_200_OK,
            )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/backtesting/verify/
# ─────────────────────────────────────────────────────────────────────────────

class TriggerVerificationView(APIView):
    """
    Triggers prediction verification.
    Body: { "metal": "gold", "timeframe": "1d" }
    """

    def post(self, request):
        metal = request.data.get("metal", "gold")
        timeframe = request.data.get("timeframe", "1d")

        if metal not in ("gold", "silver"):
            return Response(
                {"error": "metal must be 'gold' or 'silver'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from oracle.tasks_backtest import verify_predictions_task
            task = verify_predictions_task.delay(metal=metal, timeframe=timeframe)
            return Response(
                {"status": "queued", "task_id": task.id},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception:
            from oracle.services.prediction_verification import verify_predictions
            stats = verify_predictions(metal=metal, timeframe=timeframe)
            return Response(
                {
                    "status": "completed",
                    "total_verified": stats.total_verified,
                    "mae": stats.mae,
                    "mape": stats.mape,
                    "directional_accuracy": stats.directional_accuracy,
                },
                status=status.HTTP_200_OK,
            )
