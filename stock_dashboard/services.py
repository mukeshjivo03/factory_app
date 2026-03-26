"""
stock_dashboard/services.py

Business logic for the Stock Dashboard.
Calculates stock health ratios and categorizes items by urgency.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sap_client.context import CompanyContext

from .hana_reader import HanaStockDashboardReader

logger = logging.getLogger(__name__)


class StockDashboardService:
    """
    Orchestrates SAP HANA reads and business calculations for the stock dashboard.

    Usage:
        service = StockDashboardService(company_code="JIVO_OIL")
        result = service.get_stock_levels(filters)
    """

    def __init__(self, company_code: str):
        self.company_code = company_code
        self.context = CompanyContext(company_code)
        self.reader = HanaStockDashboardReader(self.context)

    def get_stock_levels(self, filters: Dict[str, Any]) -> Dict:
        """
        Returns stock level data with health status for each item-warehouse.

        Health logic:
          - on_hand >= min_stock        → 'healthy'
          - on_hand < min_stock          → 'low'       (below minimum)
          - on_hand < min_stock * 0.6    → 'critical'  (below 60% of minimum)
        """
        rows = self.reader.get_stock_levels(filters)

        for row in rows:
            row["stock_status"] = self._stock_status(row["on_hand"], row["min_stock"])
            row["health_ratio"] = round(
                row["on_hand"] / row["min_stock"], 2
            ) if row["min_stock"] > 0 else 0.0

        # Apply status filter (post-calculation since status is computed)
        status_filter = filters.get("status", "all")
        if status_filter and status_filter != "all":
            rows = [r for r in rows if r["stock_status"] == status_filter]

        total_items = len(rows)
        low_count = sum(1 for r in rows if r["stock_status"] == "low")
        critical_count = sum(1 for r in rows if r["stock_status"] == "critical")

        return {
            "data": rows,
            "meta": {
                "total_items": total_items,
                "low_stock_count": low_count,
                "critical_stock_count": critical_count,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def _stock_status(on_hand: float, min_stock: float) -> str:
        """
        Returns a stock health label:
          'healthy'  — on_hand >= min_stock
          'low'      — on_hand < min_stock but >= 60% of min_stock
          'critical' — on_hand < 60% of min_stock
        """
        if on_hand >= min_stock:
            return "healthy"
        if on_hand >= min_stock * 0.6:
            return "low"
        return "critical"
