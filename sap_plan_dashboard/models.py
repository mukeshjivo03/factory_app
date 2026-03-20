"""
sap_plan_dashboard/models.py

No database tables needed — all data is read live from SAP HANA.
This module exists solely to define custom permissions for the app.
"""

from django.db import models


class PlanDashboardPermission(models.Model):
    """
    Sentinel model that holds custom permissions for the Plan Dashboard.
    No database rows are ever written to this table.
    """

    class Meta:
        managed = False  # No DB table created
        default_permissions = ()  # Don't generate add/view/change/delete
        permissions = [
            ("can_view_plan_dashboard", "Can view SAP Plan Dashboard"),
            ("can_export_plan_dashboard", "Can export SAP Plan Dashboard data"),
        ]
