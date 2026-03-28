from django.urls import path

from .views import InventoryAgeDashboardAPI

urlpatterns = [
    path("", InventoryAgeDashboardAPI.as_view(), name="inventory-age-dashboard"),
]
