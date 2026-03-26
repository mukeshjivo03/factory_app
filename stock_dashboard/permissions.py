# stock_dashboard/permissions.py
"""
Permission-based access control for Stock Dashboard module.
Uses Django's built-in permission system.
"""

from rest_framework.permissions import BasePermission


class CanViewStockDashboard(BasePermission):
    """Permission to view the Stock Dashboard."""

    def has_permission(self, request, view):
        return request.user.has_perm("stock_dashboard.can_view_stock_dashboard")
