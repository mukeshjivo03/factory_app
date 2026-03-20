"""
sap_plan_dashboard/services.py

Business logic for the SAP Plan Dashboard.
Aggregates production order data, calculates procurement shortfalls,
and formats responses for the API layer.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sap_client.context import CompanyContext
from sap_client.exceptions import SAPConnectionError, SAPDataError

from .hana_reader import HanaPlanDashboardReader

logger = logging.getLogger(__name__)


class PlanDashboardService:
    """
    Orchestrates SAP HANA reads and business calculations for the plan dashboard.

    Usage:
        service = PlanDashboardService(company_code="JIVO_OIL")
        summary = service.get_summary(filters)
    """

    def __init__(self, company_code: str):
        self.company_code = company_code
        self.context = CompanyContext(company_code)
        self.reader = HanaPlanDashboardReader(self.context)

    # ------------------------------------------------------------------
    # Summary — one row per production order
    # ------------------------------------------------------------------

    def get_summary(self, filters: Dict[str, Any]) -> Dict:
        """
        Returns SKU-level summary of all open production orders.

        Each row represents one production order with aggregated
        component shortfall counts.
        """
        rows = self.reader.get_summary(filters)

        total_orders = len(rows)
        orders_with_shortfall = sum(
            1 for r in rows if r["components_with_shortfall"] > 0
        )

        return {
            "data": rows,
            "meta": {
                "total_orders": total_orders,
                "orders_with_shortfall": orders_with_shortfall,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Details — full BOM explosion
    # ------------------------------------------------------------------

    def get_details(self, filters: Dict[str, Any]) -> Dict:
        """
        Returns all BOM component rows across open production orders,
        grouped by production order.

        Optionally filters to show only components with shortfall.
        """
        rows = self.reader.get_details(filters)
        show_shortfall_only = filters.get("show_shortfall_only", False)

        if show_shortfall_only:
            rows = [r for r in rows if r["shortfall_qty"] > 0]

        grouped = self._group_details_by_order(rows)

        return {
            "data": grouped,
            "meta": {
                "total_orders": len(grouped),
                "total_component_lines": len(rows),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Procurement — aggregated shortfall per component
    # ------------------------------------------------------------------

    def get_procurement(self, filters: Dict[str, Any]) -> Dict:
        """
        Returns aggregated purchase requirements across all open orders.

        Each row represents one component with:
          - total_required_qty  = sum of remaining required across all orders
          - net_available       = OnHand - IsCommited (from OITM)
          - shortfall_qty       = max(0, total_required - net_available)
          - suggested_purchase_qty = shortfall_qty (frontend can apply safety buffer)
          - related_prod_orders = list of production order numbers that need this item
        """
        # Fetch all detail rows (unfiltered by shortfall — we aggregate first)
        detail_filters = {k: v for k, v in filters.items() if k != "show_shortfall_only"}
        rows = self.reader.get_details(detail_filters)

        # Only consider lines with remaining work
        rows = [r for r in rows if r["component_remaining_qty"] > 0]

        procurement = self._aggregate_procurement(rows)

        show_shortfall_only = filters.get("show_shortfall_only", False)
        if show_shortfall_only:
            procurement = [p for p in procurement if p["shortfall_qty"] > 0]

        # Sort: worst shortfalls first, then by total required desc
        procurement.sort(
            key=lambda x: (-x["shortfall_qty"], -x["total_required_qty"])
        )

        components_with_shortfall = sum(1 for p in procurement if p["shortfall_qty"] > 0)

        return {
            "data": procurement,
            "meta": {
                "total_components": len(procurement),
                "components_with_shortfall": components_with_shortfall,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Single SKU Detail
    # ------------------------------------------------------------------

    def get_sku_detail(self, doc_entry: int) -> Dict:
        """
        Returns full BOM explosion for a single production order.
        Raises ValueError if the order is not found or not open.
        """
        rows = self.reader.get_sku_detail(doc_entry)

        if not rows:
            raise ValueError(
                f"Production order {doc_entry} not found or is not in Planned/Released status."
            )

        order_header = {
            "prod_order_entry": rows[0]["prod_order_entry"],
            "prod_order_num": rows[0]["prod_order_num"],
            "sku_code": rows[0]["sku_code"],
            "sku_name": rows[0]["sku_name"],
            "sku_planned_qty": rows[0]["sku_planned_qty"],
            "sku_completed_qty": rows[0]["sku_completed_qty"],
            "status": rows[0]["prod_order_status"],
            "due_date": rows[0]["due_date"],
            "post_date": rows[0]["post_date"],
            "warehouse": rows[0]["prod_warehouse"],
            "priority": rows[0]["priority"],
        }

        components = [
            {
                "component_line": r["component_line"],
                "component_code": r["component_code"],
                "component_name": r["component_name"],
                "component_planned_qty": r["component_planned_qty"],
                "component_issued_qty": r["component_issued_qty"],
                "component_remaining_qty": r["component_remaining_qty"],
                "component_warehouse": r["component_warehouse"],
                "base_qty": r["base_qty"],
                "uom": r["uom"],
                "stock_on_hand": r["stock_on_hand"],
                "stock_committed": r["stock_committed"],
                "stock_on_order": r["stock_on_order"],
                "net_available": r["net_available"],
                "shortfall_qty": r["shortfall_qty"],
                "vendor_lead_time": r["vendor_lead_time"],
                "default_vendor": r["default_vendor"],
                "stock_status": self._stock_status(r["net_available"], r["component_remaining_qty"]),
            }
            for r in rows
        ]

        total_components = len(components)
        components_with_shortfall = sum(1 for c in components if c["shortfall_qty"] > 0)

        return {
            "data": {
                **order_header,
                "total_components": total_components,
                "components_with_shortfall": components_with_shortfall,
                "components": components,
            },
            "meta": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _group_details_by_order(self, rows: List[Dict]) -> List[Dict]:
        """Groups flat component rows into nested production order objects."""
        orders: Dict[int, Dict] = {}

        for row in rows:
            entry = row["prod_order_entry"]

            if entry not in orders:
                orders[entry] = {
                    "prod_order_entry": entry,
                    "prod_order_num": row["prod_order_num"],
                    "sku_code": row["sku_code"],
                    "sku_name": row["sku_name"],
                    "sku_planned_qty": row["sku_planned_qty"],
                    "sku_completed_qty": row["sku_completed_qty"],
                    "status": row["prod_order_status"],
                    "due_date": row["due_date"],
                    "post_date": row["post_date"],
                    "warehouse": row["prod_warehouse"],
                    "priority": row["priority"],
                    "components": [],
                }

            orders[entry]["components"].append(
                {
                    "component_line": row["component_line"],
                    "component_code": row["component_code"],
                    "component_name": row["component_name"],
                    "component_planned_qty": row["component_planned_qty"],
                    "component_issued_qty": row["component_issued_qty"],
                    "component_remaining_qty": row["component_remaining_qty"],
                    "component_warehouse": row["component_warehouse"],
                    "base_qty": row["base_qty"],
                    "uom": row["uom"],
                    "stock_on_hand": row["stock_on_hand"],
                    "stock_committed": row["stock_committed"],
                    "stock_on_order": row["stock_on_order"],
                    "net_available": row["net_available"],
                    "shortfall_qty": row["shortfall_qty"],
                    "vendor_lead_time": row["vendor_lead_time"],
                    "default_vendor": row["default_vendor"],
                    "stock_status": self._stock_status(
                        row["net_available"], row["component_remaining_qty"]
                    ),
                }
            )

        # Annotate each order with its shortfall count
        result = list(orders.values())
        for order in result:
            order["total_components"] = len(order["components"])
            order["components_with_shortfall"] = sum(
                1 for c in order["components"] if c["shortfall_qty"] > 0
            )

        return result

    def _aggregate_procurement(self, rows: List[Dict]) -> List[Dict]:
        """
        Aggregates detail rows by component code.

        Returns one dict per unique component with:
          - Summed required quantities across all orders
          - Latest stock levels (same across all rows for a given item)
          - Calculated shortfall and suggested purchase qty
          - List of related production order numbers
        """
        agg: Dict[str, Dict] = {}

        for row in rows:
            code = row["component_code"]

            if code not in agg:
                agg[code] = {
                    "component_code": code,
                    "component_name": row["component_name"],
                    "uom": row["uom"],
                    "total_required_qty": 0.0,
                    "stock_on_hand": row["stock_on_hand"],
                    "stock_committed": row["stock_committed"],
                    "stock_on_order": row["stock_on_order"],
                    "net_available": row["net_available"],
                    "vendor_lead_time": row["vendor_lead_time"],
                    "default_vendor": row["default_vendor"],
                    "related_prod_orders": [],
                }

            agg[code]["total_required_qty"] += row["component_remaining_qty"]

            prod_order_num = str(row["prod_order_num"])
            if prod_order_num not in agg[code]["related_prod_orders"]:
                agg[code]["related_prod_orders"].append(prod_order_num)

        # Calculate shortfall and suggested purchase qty
        result = []
        for code, data in agg.items():
            shortfall = max(0.0, data["total_required_qty"] - data["net_available"])
            data["shortfall_qty"] = round(shortfall, 4)
            data["suggested_purchase_qty"] = round(shortfall, 4)
            data["total_required_qty"] = round(data["total_required_qty"], 4)
            result.append(data)

        return result

    @staticmethod
    def _stock_status(net_available: float, required: float) -> str:
        """
        Returns a stock health label:
          'sufficient' — net_available >= required
          'partial'    — net_available > 0 but < required
          'stockout'   — net_available <= 0
        """
        if net_available >= required:
            return "sufficient"
        if net_available > 0:
            return "partial"
        return "stockout"
