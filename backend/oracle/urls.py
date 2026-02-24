from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.HealthView.as_view()),
    path('price/<str:metal>/', views.CurrentPriceView.as_view()),
    path('historical/<str:metal>/', views.HistoricalView.as_view()),
    path('indicators/<str:metal>/', views.IndicatorsView.as_view()),
    path('predictions/<str:metal>/', views.PredictionsView.as_view()),
    path('refresh/', views.RefreshView.as_view()),
    path('sentiment/<str:metal>/', views.SentimentView.as_view()),
]
