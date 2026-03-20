from django.urls import path

from .views import (
    PlanDashboardSummaryAPI,
    PlanDashboardDetailsAPI,
    PlanDashboardProcurementAPI,
    PlanDashboardSKUDetailAPI,
)

urlpatterns = [
    path("summary/", PlanDashboardSummaryAPI.as_view(), name="plan-dashboard-summary"),
    path("details/", PlanDashboardDetailsAPI.as_view(), name="plan-dashboard-details"),
    path("procurement/", PlanDashboardProcurementAPI.as_view(), name="plan-dashboard-procurement"),
    path("sku/<int:doc_entry>/", PlanDashboardSKUDetailAPI.as_view(), name="plan-dashboard-sku-detail"),
]
