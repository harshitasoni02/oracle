from rest_framework import serializers
from .models import PriceSnapshot, PriceBar, IndicatorSnapshot, Prediction


class PriceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSnapshot
        fields = '__all__'


class PriceBarSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceBar
        fields = ['timestamp', 'open_usd', 'high_usd', 'low_usd', 'close_usd', 'volume', 'close_inr']


class IndicatorSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndicatorSnapshot
        fields = '__all__'


class PredictionSerializer(serializers.ModelSerializer):
    timeframe_label = serializers.SerializerMethodField()

    class Meta:
        model = Prediction
        fields = '__all__'

    def get_timeframe_label(self, obj):
        labels = {
            '1d': 'Tomorrow',
            '1w': 'Next Week',
            '2w': 'In 2 Weeks',
            '1m': 'Next Month',
            '3m': 'In 3 Months',
            '6m': 'In 6 Months',
            '1y': 'In 1 Year',
        }
        return labels.get(obj.timeframe, obj.timeframe)
