"""
sap_plan_dashboard/tests.py

Unit tests for the SAP Plan Dashboard app.

Tests cover:
  1. HanaPlanDashboardReader — row mapping and query building
  2. PlanDashboardService    — aggregation, calculations, edge cases
  3. API views               — response shape, auth, filter validation
"""

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_detail_row(
    *,
    prod_order_entry=1,
    prod_order_num=101,
    sku_code="FG-001",
    sku_name="Protein Bar",
    sku_planned_qty=500.0,
    sku_completed_qty=0.0,
    prod_order_status="P",
    due_date=date(2026, 3, 20),
    post_date=date(2026, 3, 13),
    prod_warehouse="WH-01",
    priority=2,
    component_line=0,
    component_code="RM-042",
    component_name="Oat Flour",
    component_planned_qty=125.0,
    component_issued_qty=0.0,
    component_warehouse="RM-WH",
    base_qty=0.25,
    uom="KG",
    stock_on_hand=300.0,
    stock_committed=80.0,
    stock_on_order=200.0,
    vendor_lead_time=7,
    default_vendor="V-001",
):
    """Returns a tuple in the same column order as HanaPlanDashboardReader._map_detail_row."""
    return (
        prod_order_entry,    # 0
        prod_order_num,      # 1
        sku_code,            # 2
        sku_name,            # 3
        sku_planned_qty,     # 4
        sku_completed_qty,   # 5
        prod_order_status,   # 6
        due_date,            # 7
        post_date,           # 8
        prod_warehouse,      # 9
        priority,            # 10
        component_line,      # 11
        component_code,      # 12
        component_name,      # 13
        component_planned_qty,  # 14
        component_issued_qty,   # 15
        component_planned_qty - component_issued_qty,  # 16 remaining
        component_warehouse,    # 17
        base_qty,            # 18
        uom,                 # 19
        stock_on_hand,       # 20
        stock_committed,     # 21
        stock_on_order,      # 22
        stock_on_hand - stock_committed,  # 23 net_available
        vendor_lead_time,    # 24
        default_vendor,      # 25
    )


def _make_summary_row(
    *,
    prod_order_entry=1,
    prod_order_num=101,
    sku_code="FG-001",
    sku_name="Protein Bar",
    planned_qty=500.0,
    completed_qty=0.0,
    status="P",
    due_date=date(2026, 3, 20),
    post_date=date(2026, 3, 13),
    priority=2,
    warehouse="WH-01",
    total_components=3,
    components_with_shortfall=1,
    total_remaining=375.0,
):
    return (
        prod_order_entry, prod_order_num, sku_code, sku_name,
        planned_qty, completed_qty, status,
        due_date, post_date, priority, warehouse,
        total_components, components_with_shortfall, total_remaining,
    )


# ---------------------------------------------------------------------------
# 1. HanaPlanDashboardReader Tests
# ---------------------------------------------------------------------------


class TestHanaPlanDashboardReaderRowMapping(TestCase):
    """Tests for _map_detail_row and _map_summary_row."""

    def setUp(self):
        from sap_plan_dashboard.hana_reader import HanaPlanDashboardReader

        context = MagicMock()
        context.hana = {"host": "localhost", "port": 30015, "user": "u", "password": "p", "schema": "TEST"}
        with patch("sap_plan_dashboard.hana_reader.HanaConnection"):
            self.reader = HanaPlanDashboardReader(context)
            self.reader.connection.schema = "TEST"

    def test_map_detail_row_basic_fields(self):
        row = _make_detail_row()
        result = self.reader._map_detail_row(row)

        self.assertEqual(result["prod_order_entry"], 1)
        self.assertEqual(result["prod_order_num"], 101)
        self.assertEqual(result["sku_code"], "FG-001")
        self.assertEqual(result["component_code"], "RM-042")
        self.assertEqual(result["component_name"], "Oat Flour")
        self.assertEqual(result["uom"], "KG")

    def test_map_detail_row_calculates_remaining_qty(self):
        row = _make_detail_row(component_planned_qty=125.0, component_issued_qty=25.0)
        result = self.reader._map_detail_row(row)
        self.assertEqual(result["component_remaining_qty"], 100.0)

    def test_map_detail_row_calculates_net_available(self):
        row = _make_detail_row(stock_on_hand=300.0, stock_committed=80.0)
        result = self.reader._map_detail_row(row)
        self.assertEqual(result["net_available"], 220.0)

    def test_map_detail_row_no_shortfall_when_sufficient(self):
        # required=125, net_available=300-80=220 → no shortfall
        row = _make_detail_row(
            component_planned_qty=125.0,
            component_issued_qty=0.0,
            stock_on_hand=300.0,
            stock_committed=80.0,
        )
        result = self.reader._map_detail_row(row)
        self.assertEqual(result["shortfall_qty"], 0.0)

    def test_map_detail_row_shortfall_when_insufficient(self):
        # required=125, net_available=20-0=20 → shortfall=105
        row = _make_detail_row(
            component_planned_qty=125.0,
            component_issued_qty=0.0,
            stock_on_hand=20.0,
            stock_committed=0.0,
        )
        result = self.reader._map_detail_row(row)
        self.assertEqual(result["shortfall_qty"], 105.0)

    def test_map_detail_row_shortfall_never_negative(self):
        # required=50, net_available=200 → shortfall=0 (not -150)
        row = _make_detail_row(
            component_planned_qty=50.0,
            component_issued_qty=0.0,
            stock_on_hand=200.0,
            stock_committed=0.0,
        )
        result = self.reader._map_detail_row(row)
        self.assertEqual(result["shortfall_qty"], 0.0)

    def test_map_detail_row_status_mapping(self):
        row = _make_detail_row(prod_order_status="P")
        self.assertEqual(self.reader._map_detail_row(row)["prod_order_status"], "planned")

        row = _make_detail_row(prod_order_status="R")
        self.assertEqual(self.reader._map_detail_row(row)["prod_order_status"], "released")

    def test_map_detail_row_due_date_format(self):
        row = _make_detail_row(due_date=date(2026, 3, 20))
        result = self.reader._map_detail_row(row)
        self.assertEqual(result["due_date"], "2026-03-20")

    def test_map_detail_row_none_due_date(self):
        row = _make_detail_row(due_date=None)
        result = self.reader._map_detail_row(row)
        self.assertIsNone(result["due_date"])

    def test_map_summary_row_basic(self):
        row = _make_summary_row()
        result = self.reader._map_summary_row(row)

        self.assertEqual(result["prod_order_entry"], 1)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["total_components"], 3)
        self.assertEqual(result["components_with_shortfall"], 1)

    def test_map_status_unknown_value(self):
        self.assertEqual(self.reader._map_status("X"), "X")
        self.assertEqual(self.reader._map_status(""), "")


# ---------------------------------------------------------------------------
# 2. PlanDashboardService Tests
# ---------------------------------------------------------------------------


class TestPlanDashboardServiceAggregation(TestCase):
    """Tests for service-level aggregation and calculation logic."""

    def _make_service(self):
        from sap_plan_dashboard.services import PlanDashboardService

        with patch("sap_plan_dashboard.services.CompanyContext"), \
             patch("sap_plan_dashboard.services.HanaPlanDashboardReader"):
            service = PlanDashboardService.__new__(PlanDashboardService)
            service.company_code = "JIVO_OIL"
            service.reader = MagicMock()
            return service

    def test_get_summary_meta_counts(self):
        service = self._make_service()
        service.reader.get_summary.return_value = [
            {"components_with_shortfall": 2},
            {"components_with_shortfall": 0},
            {"components_with_shortfall": 1},
        ]
        result = service.get_summary({})

        self.assertEqual(result["meta"]["total_orders"], 3)
        self.assertEqual(result["meta"]["orders_with_shortfall"], 2)

    def test_get_procurement_aggregates_correctly(self):
        service = self._make_service()
        # Two orders both needing RM-042
        service.reader.get_details.return_value = [
            {
                "component_code": "RM-042",
                "component_name": "Oat Flour",
                "uom": "KG",
                "component_remaining_qty": 100.0,
                "stock_on_hand": 300.0,
                "stock_committed": 80.0,
                "stock_on_order": 0.0,
                "net_available": 220.0,
                "vendor_lead_time": 7,
                "default_vendor": "V-001",
                "prod_order_num": 101,
            },
            {
                "component_code": "RM-042",
                "component_name": "Oat Flour",
                "uom": "KG",
                "component_remaining_qty": 200.0,
                "stock_on_hand": 300.0,
                "stock_committed": 80.0,
                "stock_on_order": 0.0,
                "net_available": 220.0,
                "vendor_lead_time": 7,
                "default_vendor": "V-001",
                "prod_order_num": 102,
            },
        ]
        result = service.get_procurement({})
        items = result["data"]

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["component_code"], "RM-042")
        self.assertEqual(item["total_required_qty"], 300.0)
        self.assertEqual(item["net_available"], 220.0)
        # shortfall = 300 - 220 = 80
        self.assertEqual(item["shortfall_qty"], 80.0)
        self.assertEqual(item["suggested_purchase_qty"], 80.0)
        self.assertIn("101", item["related_prod_orders"])
        self.assertIn("102", item["related_prod_orders"])

    def test_get_procurement_no_shortfall(self):
        service = self._make_service()
        service.reader.get_details.return_value = [
            {
                "component_code": "RM-001",
                "component_name": "Sugar",
                "uom": "KG",
                "component_remaining_qty": 50.0,
                "stock_on_hand": 500.0,
                "stock_committed": 100.0,
                "stock_on_order": 0.0,
                "net_available": 400.0,
                "vendor_lead_time": 3,
                "default_vendor": "V-002",
                "prod_order_num": 101,
            }
        ]
        result = service.get_procurement({})
        item = result["data"][0]

        self.assertEqual(item["shortfall_qty"], 0.0)
        self.assertEqual(result["meta"]["components_with_shortfall"], 0)

    def test_get_procurement_excludes_zero_remaining(self):
        service = self._make_service()
        service.reader.get_details.return_value = [
            {
                "component_code": "RM-001",
                "component_name": "Sugar",
                "uom": "KG",
                "component_remaining_qty": 0.0,  # fully issued
                "stock_on_hand": 100.0,
                "stock_committed": 0.0,
                "stock_on_order": 0.0,
                "net_available": 100.0,
                "vendor_lead_time": 3,
                "default_vendor": "V-002",
                "prod_order_num": 101,
            }
        ]
        result = service.get_procurement({})
        self.assertEqual(len(result["data"]), 0)

    def test_get_procurement_sorted_worst_first(self):
        service = self._make_service()
        service.reader.get_details.return_value = [
            {
                "component_code": "RM-A",
                "component_name": "A",
                "uom": "KG",
                "component_remaining_qty": 100.0,
                "stock_on_hand": 90.0,
                "stock_committed": 0.0,
                "stock_on_order": 0.0,
                "net_available": 90.0,
                "vendor_lead_time": 1,
                "default_vendor": "",
                "prod_order_num": 101,
            },
            {
                "component_code": "RM-B",
                "component_name": "B",
                "uom": "KG",
                "component_remaining_qty": 500.0,
                "stock_on_hand": 50.0,
                "stock_committed": 0.0,
                "stock_on_order": 0.0,
                "net_available": 50.0,
                "vendor_lead_time": 1,
                "default_vendor": "",
                "prod_order_num": 101,
            },
        ]
        result = service.get_procurement({})
        codes = [item["component_code"] for item in result["data"]]
        # RM-B shortfall=450 > RM-A shortfall=10 → RM-B comes first
        self.assertEqual(codes[0], "RM-B")

    def test_get_procurement_show_shortfall_only_filter(self):
        service = self._make_service()
        service.reader.get_details.return_value = [
            {
                "component_code": "RM-FINE",
                "component_name": "Fine",
                "uom": "KG",
                "component_remaining_qty": 50.0,
                "stock_on_hand": 500.0,
                "stock_committed": 0.0,
                "stock_on_order": 0.0,
                "net_available": 500.0,
                "vendor_lead_time": 1,
                "default_vendor": "",
                "prod_order_num": 101,
            },
            {
                "component_code": "RM-SHORT",
                "component_name": "Short",
                "uom": "KG",
                "component_remaining_qty": 200.0,
                "stock_on_hand": 10.0,
                "stock_committed": 0.0,
                "stock_on_order": 0.0,
                "net_available": 10.0,
                "vendor_lead_time": 1,
                "default_vendor": "",
                "prod_order_num": 101,
            },
        ]
        result = service.get_procurement({"show_shortfall_only": True})
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["component_code"], "RM-SHORT")

    def test_get_sku_detail_raises_on_missing(self):
        service = self._make_service()
        service.reader.get_sku_detail.return_value = []

        with self.assertRaises(ValueError) as ctx:
            service.get_sku_detail(9999)
        self.assertIn("9999", str(ctx.exception))

    def test_stock_status_sufficient(self):
        from sap_plan_dashboard.services import PlanDashboardService
        self.assertEqual(PlanDashboardService._stock_status(220.0, 125.0), "sufficient")

    def test_stock_status_partial(self):
        from sap_plan_dashboard.services import PlanDashboardService
        self.assertEqual(PlanDashboardService._stock_status(50.0, 125.0), "partial")

    def test_stock_status_stockout(self):
        from sap_plan_dashboard.services import PlanDashboardService
        self.assertEqual(PlanDashboardService._stock_status(0.0, 125.0), "stockout")
        self.assertEqual(PlanDashboardService._stock_status(-5.0, 125.0), "stockout")

    def test_stock_status_exact_match(self):
        from sap_plan_dashboard.services import PlanDashboardService
        self.assertEqual(PlanDashboardService._stock_status(125.0, 125.0), "sufficient")

    def test_get_details_show_shortfall_only(self):
        service = self._make_service()
        service.reader.get_details.return_value = [
            {
                "prod_order_entry": 1,
                "prod_order_num": 101,
                "sku_code": "FG-001",
                "sku_name": "Bar",
                "sku_planned_qty": 500.0,
                "sku_completed_qty": 0.0,
                "prod_order_status": "planned",
                "due_date": "2026-03-20",
                "post_date": "2026-03-13",
                "prod_warehouse": "WH-01",
                "priority": 2,
                "component_line": 0,
                "component_code": "RM-FINE",
                "component_name": "Fine",
                "component_planned_qty": 50.0,
                "component_issued_qty": 0.0,
                "component_remaining_qty": 50.0,
                "component_warehouse": "RM-WH",
                "base_qty": 0.1,
                "uom": "KG",
                "stock_on_hand": 500.0,
                "stock_committed": 0.0,
                "stock_on_order": 0.0,
                "net_available": 500.0,
                "vendor_lead_time": 1,
                "default_vendor": "",
                "shortfall_qty": 0.0,
            }
        ]
        result = service.get_details({"show_shortfall_only": True})
        # The only component has no shortfall, so no orders should appear
        self.assertEqual(len(result["data"]), 0)

    def test_get_sku_detail_structure(self):
        service = self._make_service()
        service.reader.get_sku_detail.return_value = [
            {
                "prod_order_entry": 1,
                "prod_order_num": 101,
                "sku_code": "FG-001",
                "sku_name": "Protein Bar",
                "sku_planned_qty": 500.0,
                "sku_completed_qty": 0.0,
                "prod_order_status": "planned",
                "due_date": "2026-03-20",
                "post_date": "2026-03-13",
                "prod_warehouse": "WH-01",
                "priority": 2,
                "component_line": 0,
                "component_code": "RM-042",
                "component_name": "Oat Flour",
                "component_planned_qty": 125.0,
                "component_issued_qty": 0.0,
                "component_remaining_qty": 125.0,
                "component_warehouse": "RM-WH",
                "base_qty": 0.25,
                "uom": "KG",
                "stock_on_hand": 300.0,
                "stock_committed": 80.0,
                "stock_on_order": 200.0,
                "net_available": 220.0,
                "vendor_lead_time": 7,
                "default_vendor": "V-001",
                "shortfall_qty": 0.0,
            }
        ]
        result = service.get_sku_detail(1)

        self.assertEqual(result["data"]["prod_order_entry"], 1)
        self.assertEqual(result["data"]["total_components"], 1)
        self.assertEqual(result["data"]["components_with_shortfall"], 0)
        self.assertEqual(result["data"]["components"][0]["component_code"], "RM-042")
        self.assertIn("fetched_at", result["meta"])


# ---------------------------------------------------------------------------
# 3. Filter Serializer Tests
# ---------------------------------------------------------------------------


class TestPlanDashboardFilterSerializer(TestCase):

    def setUp(self):
        from sap_plan_dashboard.serializers import PlanDashboardFilterSerializer
        self.Serializer = PlanDashboardFilterSerializer

    def test_valid_defaults(self):
        s = self.Serializer(data={})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["status"], "all")
        self.assertFalse(s.validated_data["show_shortfall_only"])

    def test_valid_full_params(self):
        s = self.Serializer(data={
            "status": "planned",
            "due_date_from": "2026-03-01",
            "due_date_to": "2026-03-31",
            "warehouse": "WH-01",
            "sku": "FG-001",
            "show_shortfall_only": "true",
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_status(self):
        s = self.Serializer(data={"status": "completed"})
        self.assertFalse(s.is_valid())
        self.assertIn("status", s.errors)

    def test_date_range_validation_from_after_to(self):
        s = self.Serializer(data={
            "due_date_from": "2026-03-31",
            "due_date_to": "2026-03-01",
        })
        self.assertFalse(s.is_valid())

    def test_date_range_equal_is_valid(self):
        s = self.Serializer(data={
            "due_date_from": "2026-03-15",
            "due_date_to": "2026-03-15",
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_date_format(self):
        s = self.Serializer(data={"due_date_from": "15-03-2026"})
        self.assertFalse(s.is_valid())


# ---------------------------------------------------------------------------
# 4. API View Tests (with mocked service)
# ---------------------------------------------------------------------------


class TestPlanDashboardAPIViews(APITestCase):
    """
    Tests API views by mocking PlanDashboardService to avoid real SAP calls.
    Also tests auth and company-context enforcement.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from company.models import Company, UserCompany, UserRole

        User = get_user_model()
        self.user = User.objects.create_user(
            email="planner@test.com",
            password="testpass123",
            full_name="Test Planner",
            employee_code="EMP001",
        )
        # Assign permissions — use the PlanDashboardPermission content type
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from sap_plan_dashboard.models import PlanDashboardPermission

        ct = ContentType.objects.get_for_model(PlanDashboardPermission)
        perm, _ = Permission.objects.get_or_create(
            codename="can_view_plan_dashboard",
            content_type=ct,
            defaults={"name": "Can view SAP Plan Dashboard"},
        )
        self.user.user_permissions.add(perm)
        self.user.save()

        # Create company and link user
        self.company = Company.objects.create(
            name="Jivo Oil", code="JIVO_OIL", is_active=True
        )
        role = UserRole.objects.create(name="Planner")
        UserCompany.objects.create(
            user=self.user,
            company=self.company,
            role=role,
            is_default=True,
            is_active=True,
        )

        # Get JWT token
        refresh = RefreshToken.for_user(self.user)
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}",
            HTTP_COMPANY_CODE="JIVO_OIL",
        )

    def _mock_summary_response(self):
        return {
            "data": [
                {
                    "prod_order_entry": 1,
                    "prod_order_num": 101,
                    "sku_code": "FG-001",
                    "sku_name": "Protein Bar",
                    "planned_qty": 500.0,
                    "completed_qty": 0.0,
                    "status": "planned",
                    "due_date": "2026-03-20",
                    "post_date": "2026-03-13",
                    "priority": 2,
                    "warehouse": "WH-01",
                    "total_components": 3,
                    "components_with_shortfall": 1,
                    "total_remaining_component_qty": 375.0,
                }
            ],
            "meta": {
                "total_orders": 1,
                "orders_with_shortfall": 1,
                "fetched_at": "2026-03-13T10:30:00+00:00",
            },
        }

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_summary_returns_200(self, MockService):
        MockService.return_value.get_summary.return_value = self._mock_summary_response()
        response = self.client.get("/api/v1/sap/plan-dashboard/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertIn("meta", response.data)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_summary_with_filters(self, MockService):
        MockService.return_value.get_summary.return_value = self._mock_summary_response()
        response = self.client.get(
            "/api/v1/sap/plan-dashboard/summary/",
            {"status": "planned", "due_date_from": "2026-03-01", "due_date_to": "2026-03-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        call_args = MockService.return_value.get_summary.call_args[0][0]
        self.assertEqual(call_args["status"], "planned")

    def test_summary_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/v1/sap/plan-dashboard/summary/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_summary_requires_company_code(self):
        client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = client.get("/api/v1/sap/plan-dashboard/summary/")
        # HasCompanyContext returns 403 when Company-Code header is missing
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_summary_invalid_filter_returns_400(self, MockService):
        response = self.client.get(
            "/api/v1/sap/plan-dashboard/summary/",
            {"status": "invalid_choice"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_summary_sap_connection_error_returns_503(self, MockService):
        from sap_client.exceptions import SAPConnectionError
        MockService.return_value.get_summary.side_effect = SAPConnectionError("down")
        response = self.client.get("/api/v1/sap/plan-dashboard/summary/")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_summary_sap_data_error_returns_502(self, MockService):
        from sap_client.exceptions import SAPDataError
        MockService.return_value.get_summary.side_effect = SAPDataError("bad data")
        response = self.client.get("/api/v1/sap/plan-dashboard/summary/")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_procurement_returns_200(self, MockService):
        MockService.return_value.get_procurement.return_value = {
            "data": [],
            "meta": {
                "total_components": 0,
                "components_with_shortfall": 0,
                "fetched_at": "2026-03-13T10:30:00+00:00",
            },
        }
        response = self.client.get("/api/v1/sap/plan-dashboard/procurement/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_sku_detail_returns_200(self, MockService):
        MockService.return_value.get_sku_detail.return_value = {
            "data": {
                "prod_order_entry": 1,
                "prod_order_num": 101,
                "sku_code": "FG-001",
                "sku_name": "Protein Bar",
                "sku_planned_qty": 500.0,
                "sku_completed_qty": 0.0,
                "status": "planned",
                "due_date": "2026-03-20",
                "post_date": "2026-03-13",
                "warehouse": "WH-01",
                "priority": 2,
                "total_components": 1,
                "components_with_shortfall": 0,
                "components": [],
            },
            "meta": {"fetched_at": "2026-03-13T10:30:00+00:00"},
        }
        response = self.client.get("/api/v1/sap/plan-dashboard/sku/1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_sku_detail_not_found_returns_404(self, MockService):
        MockService.return_value.get_sku_detail.side_effect = ValueError("Not found")
        response = self.client.get("/api/v1/sap/plan-dashboard/sku/9999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("sap_plan_dashboard.views.PlanDashboardService")
    def test_details_returns_200(self, MockService):
        MockService.return_value.get_details.return_value = {
            "data": [],
            "meta": {
                "total_orders": 0,
                "total_component_lines": 0,
                "fetched_at": "2026-03-13T10:30:00+00:00",
            },
        }
        response = self.client.get("/api/v1/sap/plan-dashboard/details/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
