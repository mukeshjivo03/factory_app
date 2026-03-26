"""
stock_dashboard/models.py

No database tables needed — all data is read live from SAP HANA.
This module exists solely to define custom permissions for the app.
"""

from django.db import models


class StockDashboardPermission(models.Model):
    """
    Sentinel model that holds custom permissions for the Stock Dashboard.
    No database rows are ever written to this table.
    """

    class Meta:
        managed = False  # No DB table created
        default_permissions = ()  # Don't generate add/view/change/delete
        permissions = [
            ("can_view_stock_dashboard", "Can view Stock Dashboard"),
        ]
