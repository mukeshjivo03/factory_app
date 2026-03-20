# sap_plan_dashboard/permissions.py
"""
Permission-based access control for SAP Plan Dashboard module.
Uses Django's built-in permission system.
"""

from rest_framework.permissions import BasePermission


class CanViewPlanDashboard(BasePermission):
    """Permission to view the SAP Plan Dashboard."""

    def has_permission(self, request, view):
        return request.user.has_perm("sap_plan_dashboard.can_view_plan_dashboard")


class CanExportPlanDashboard(BasePermission):
    """Permission to export procurement data from the Plan Dashboard."""

    def has_permission(self, request, view):
        return request.user.has_perm("sap_plan_dashboard.can_export_plan_dashboard")
