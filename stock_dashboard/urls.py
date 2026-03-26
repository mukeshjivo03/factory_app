from django.urls import path

from .views import StockDashboardAPI

urlpatterns = [
    path("", StockDashboardAPI.as_view(), name="stock-dashboard"),
]
