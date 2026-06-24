# backend/oracle/serializers_backtest.py
"""
Serializers for BacktestResult and PredictionVerification.
Add these to your existing serializers.py or keep them separate and import.
"""

from rest_framework import serializers

from oracle.models import BacktestResult, PredictionVerification


class BacktestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestResult
        fields = [
            "id",
            "metal",
            "timeframe",
            "strategy",
            "horizon",
            "accuracy",
            "win_rate",
            "total_trades",
            "avg_gain",
            "avg_loss",
            "profit_factor",
            "max_drawdown",
            "sharpe_ratio",
            "total_return",
            "start_date",
            "end_date",
            "created_at",
        ]
        read_only_fields = fields


class PredictionVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionVerification
        fields = [
            "id",
            "metal",
            "timeframe",
            "prediction_date",
            "target_date",
            "previous_price",
            "predicted_price",
            "actual_price",
            "predicted_direction",
            "actual_direction",
            "absolute_error",
            "percentage_error",
            "direction_correct",
            "created_at",
        ]
        read_only_fields = fields


class BacktestSummarySerializer(serializers.Serializer):
    """
    Aggregate summary returned by /api/backtesting/summary/
    """
    metal = serializers.CharField()
    timeframe = serializers.CharField()
    best_strategy = serializers.CharField()
    best_accuracy = serializers.FloatField()
    best_profit_factor = serializers.FloatField()
    total_runs = serializers.IntegerField()
    strategies = BacktestResultSerializer(many=True)


class VerificationStatsSerializer(serializers.Serializer):
    """
    Stats returned by /api/backtesting/verification/
    """
    metal = serializers.CharField()
    timeframe = serializers.CharField()
    total_verified = serializers.IntegerField()
    mae = serializers.FloatField()
    rmse = serializers.FloatField()
    mape = serializers.FloatField()
    directional_accuracy = serializers.FloatField()
    avg_overestimate = serializers.FloatField()
    recent_mae = serializers.FloatField()


class TriggerBacktestSerializer(serializers.Serializer):
    metal = serializers.ChoiceField(choices=["gold", "silver"])
    timeframe = serializers.ChoiceField(choices=["1d", "1w", "1mo"])
    horizon = serializers.ChoiceField(choices=["1d", "1w", "1mo"])
