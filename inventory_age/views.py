"""
inventory_age/views.py

API views for the Inventory Age & Value dashboard.

GET /api/v1/dashboards/inventory-age/
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from company.permissions import HasCompanyContext
from sap_client.exceptions import SAPConnectionError, SAPDataError

from .permissions import CanViewInventoryAge
from .serializers import (
    InventoryAgeFilterSerializer,
    InventoryAgeResponseSerializer,
)
from .services import InventoryAgeService

logger = logging.getLogger(__name__)


class InventoryAgeDashboardAPI(APIView):
    """
    Inventory age & value dashboard.

    Calls SP_InventoryAgeValue and returns every item-warehouse row
    with on-hand qty, stock value, age in days, and computed summaries.

    GET /api/v1/dashboards/inventory-age/

    Query parameters:
        search      — item code or name (optional)
        warehouse   — warehouse code (optional)
        item_group  — item group name (optional)
        sub_group   — sub-group name (optional)
        variety     — variety (optional)
        min_age     — minimum age in days (optional)
    """

    permission_classes = [IsAuthenticated, HasCompanyContext, CanViewInventoryAge]

    def get(self, request):
        filter_serializer = InventoryAgeFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(
                {"detail": "Invalid query parameters.", "errors": filter_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = filter_serializer.validated_data
        service = InventoryAgeService(company_code=request.company.company.code)

        try:
            result = service.get_inventory_age(filters)
        except SAPConnectionError:
            return Response(
                {"detail": "SAP system is currently unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except SAPDataError as e:
            return Response(
                {"detail": f"SAP data error: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(InventoryAgeResponseSerializer(result).data)
