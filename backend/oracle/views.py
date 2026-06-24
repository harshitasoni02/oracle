from datetime import timedelta

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import PriceSnapshot, PriceBar, IndicatorSnapshot, Prediction, SentimentSnapshot
from .serializers import (
    PriceSnapshotSerializer, PriceBarSerializer,
    IndicatorSnapshotSerializer, PredictionSerializer,
)


CHART_CONFIG = {
    # candle_size -> (bar_timeframe, lookback_days)
    '1m':  ('1m',   1),
    '5m':  ('5m',   5),
    '15m': ('15m',  5),
    '1h':  ('1h',   30),
    '1d':  ('1d',   365),
    '1w':  ('1w',  1825),
}

INDICATOR_TIMEFRAME_MAP = {
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '1h': '1h',
    '1d': '1d',
    '1w': '1w',
}


class CurrentPriceView(APIView):
    def get(self, request, metal):
        if metal not in ('gold', 'silver'):
            return Response({'error': 'Invalid metal. Use gold or silver.'}, status=400)
        try:
            snap = PriceSnapshot.objects.get(metal=metal)
            return Response(PriceSnapshotSerializer(snap).data)
        except PriceSnapshot.DoesNotExist:
            return Response({'error': 'No data yet. Refresh to fetch prices.'}, status=404)


class HistoricalView(APIView):
    def get(self, request, metal):
        if metal not in ('gold', 'silver'):
            return Response({'error': 'Invalid metal.'}, status=400)

        view_tf = request.query_params.get('timeframe', '1h')
        if view_tf not in CHART_CONFIG:
            return Response({'error': f'Invalid timeframe. Use: {list(CHART_CONFIG)}'}, status=400)

        bar_tf, days = CHART_CONFIG[view_tf]
        cutoff = timezone.now() - timedelta(days=days)

        bars = list(
            PriceBar.objects.filter(metal=metal, timeframe=bar_tf, timestamp__gte=cutoff)
            .order_by('timestamp')
            .values('timestamp', 'open_usd', 'high_usd', 'low_usd', 'close_usd', 'volume', 'close_inr')
        )
        return Response(bars)


class IndicatorsView(APIView):
    def get(self, request, metal):
        if metal not in ('gold', 'silver'):
            return Response({'error': 'Invalid metal.'}, status=400)

        view_tf = request.query_params.get('timeframe', '1d')
        bar_tf = INDICATOR_TIMEFRAME_MAP.get(view_tf, '1d')

        try:
            snap = IndicatorSnapshot.objects.get(metal=metal, timeframe=bar_tf)
            return Response(IndicatorSnapshotSerializer(snap).data)
        except IndicatorSnapshot.DoesNotExist:
            return Response({'error': 'No indicator data yet.'}, status=404)


class PredictionsView(APIView):
    def get(self, request, metal):
        if metal not in ('gold', 'silver'):
            return Response({'error': 'Invalid metal.'}, status=400)

        predictions = Prediction.objects.filter(metal=metal)
        order = {'1d': 0, '1w': 1, '2w': 2, '1m': 3, '3m': 4, '6m': 5, '1y': 6}
        predictions = sorted(predictions, key=lambda p: order.get(p.timeframe, 99))
        return Response(PredictionSerializer(predictions, many=True).data)


class RefreshView(APIView):
    def post(self, request):
        from .tasks import refresh_all
        refresh_all.delay()
        return Response({'status': 'Refresh queued. Data will update in ~30 seconds.'})


class SentimentView(APIView):
    def get(self, request, metal):
        if metal not in ('gold', 'silver'):
            return Response({'error': 'Invalid metal. Use gold or silver.'}, status=400)
        try:
            snap = SentimentSnapshot.objects.get(metal=metal)
            return Response({
                'metal': snap.metal,
                'sentiment_24h': snap.sentiment_24h,
                'sentiment_7d': snap.sentiment_7d,
                'sentiment_30d': snap.sentiment_30d,
                'count_24h': snap.count_24h,
                'count_7d': snap.count_7d,
                'sentiment_momentum': snap.sentiment_momentum,
                'signal_score': snap.signal_score,
                'signal_label': snap.signal_label,
                'category_breakdown': snap.category_breakdown,
                'top_articles': snap.top_articles,
                'updated_at': snap.updated_at,
            })
        except SentimentSnapshot.DoesNotExist:
            return Response({'signal_label': 'No data yet', 'signal_score': 0.0,
                             'count_24h': 0, 'count_7d': 0, 'top_articles': [],
                             'category_breakdown': {}})


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok', 'time': timezone.now()})
