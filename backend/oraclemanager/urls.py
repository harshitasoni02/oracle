from django.contrib import admin
from django.urls import path, include
from oracle.urls_backtest import urlpatterns as backtest_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('oracle.urls')),
] + backtest_urlpatterns
