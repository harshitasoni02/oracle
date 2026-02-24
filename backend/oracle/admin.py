from django.contrib import admin
from .models import PriceSnapshot, PriceBar, IndicatorSnapshot, Prediction

admin.site.register(PriceSnapshot)
admin.site.register(IndicatorSnapshot)
admin.site.register(Prediction)

@admin.register(PriceBar)
class PriceBarAdmin(admin.ModelAdmin):
    list_display = ['metal', 'timeframe', 'timestamp', 'close_usd', 'close_inr']
    list_filter = ['metal', 'timeframe']
    ordering = ['-timestamp']
