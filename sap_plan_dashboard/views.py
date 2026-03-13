"""
sap_plan_dashboard/views.py

API views for the SAP Plan Dashboard.

All endpoints are read-only and require:
  - JWT authentication (Authorization: Bearer <token>)
  - Company context header (Company-Code: <company_code>)
  - CanViewPlanDashboard permission
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from company.permissions import HasCompanyContext
from sap_client.exceptions import SAPConnectionError, SAPDataError

from .permissions import CanViewPlanDashboard
from .serializers import (
    PlanDashboardFilterSerializer,
    ProcurementResponseSerializer,
    DetailsResponseSerializer,
    SummaryResponseSerializer,
    SKUDetailResponseSerializer,
)
from .services import PlanDashboardService

logger = logging.getLogger(__name__)


class PlanDashboardSummaryAPI(APIView):
    """
    SKU-level summary of all open (Planned/Released) production orders.

    Returns one row per production order with aggregated component shortfall counts.

    GET /api/v1/sap/plan-dashboard/summary/

    Query parameters:
        status           — planned | released | all (default: all)
        due_date_from    — YYYY-MM-DD
        due_date_to      — YYYY-MM-DD
        warehouse        — warehouse code
        sku              — finished-good item code
        show_shortfall_only — true | false (default: false)
    """

    permission_classes = [IsAuthenticated, HasCompanyContext, CanViewPlanDashboard]

    def get(self, request):
        filter_serializer = PlanDashboardFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(
                {"detail": "Invalid query parameters.", "errors": filter_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = filter_serializer.validated_data
        service = PlanDashboardService(company_code=request.company.company.code)

        try:
            result = service.get_summary(filters)
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

        return Response(SummaryResponseSerializer(result).data)


class PlanDashboardDetailsAPI(APIView):
    """
    Full BOM explosion for all open production orders with per-line stock levels.

    Returns production orders grouped with their BOM component lines.
    Each component line includes stock-on-hand, committed, net-available, and shortfall.

    GET /api/v1/sap/plan-dashboard/details/

    Query parameters: same as /summary/ plus show_shortfall_only.
    """

    permission_classes = [IsAuthenticated, HasCompanyContext, CanViewPlanDashboard]

    def get(self, request):
        filter_serializer = PlanDashboardFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(
                {"detail": "Invalid query parameters.", "errors": filter_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = filter_serializer.validated_data
        service = PlanDashboardService(company_code=request.company.company.code)

        try:
            result = service.get_details(filters)
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

        return Response(DetailsResponseSerializer(result).data)


class PlanDashboardProcurementAPI(APIView):
    """
    Aggregated procurement / purchase requirements view.

    Each row represents one component aggregated across ALL open production orders.
    Shows total required qty, current stock, and consolidated shortfall.

    GET /api/v1/sap/plan-dashboard/procurement/

    Query parameters: same as /summary/.
    Rows are sorted by shortfall_qty DESC (worst shortfalls first).
    """

    permission_classes = [IsAuthenticated, HasCompanyContext, CanViewPlanDashboard]

    def get(self, request):
        filter_serializer = PlanDashboardFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(
                {"detail": "Invalid query parameters.", "errors": filter_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = filter_serializer.validated_data
        service = PlanDashboardService(company_code=request.company.company.code)

        try:
            result = service.get_procurement(filters)
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

        return Response(ProcurementResponseSerializer(result).data)


class PlanDashboardSKUDetailAPI(APIView):
    """
    Full component detail for a single production order.

    Returns the production order header plus all BOM component lines
    with stock and shortfall data.

    GET /api/v1/sap/plan-dashboard/sku/<doc_entry>/

    Path parameter:
        doc_entry — SAP B1 AbsoluteEntry (DocEntry) of the production order
    """

    permission_classes = [IsAuthenticated, HasCompanyContext, CanViewPlanDashboard]

    def get(self, request, doc_entry: int):
        service = PlanDashboardService(company_code=request.company.company.code)

        try:
            result = service.get_sku_detail(doc_entry)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )
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

        return Response(SKUDetailResponseSerializer(result).data)
