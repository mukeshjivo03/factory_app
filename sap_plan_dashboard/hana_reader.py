"""
sap_plan_dashboard/hana_reader.py

Executes SAP HANA SQL queries for the Plan Dashboard.
Reads directly from SAP B1 HANA tables: OWOR, WOR1, OITM, OCRD.
"""

import logging
from typing import Any, Dict, List, Optional

from hdbcli import dbapi

from sap_client.hana.connection import HanaConnection
from sap_client.exceptions import SAPConnectionError, SAPDataError

logger = logging.getLogger(__name__)


class HanaPlanDashboardReader:
    """
    Reads production order plan data directly from SAP HANA.

    Provides three queries:
      1. get_summary()      — one row per production order (SKU view)
      2. get_details()      — one row per BOM component across all orders
      3. get_sku_detail()   — BOM component rows for a single production order
    """

    def __init__(self, context):
        self.connection = HanaConnection(context.hana)

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def get_summary(self, filters: Dict[str, Any]) -> List[Dict]:
        """
        Returns one row per planned/released production order with
        component shortfall counts.

        Corresponds to SQL Query 3 — SKU Summary.
        """
        query, params = self._build_summary_query(filters)
        rows = self._execute(query, params)
        return [self._map_summary_row(r) for r in rows]

    def get_details(self, filters: Dict[str, Any]) -> List[Dict]:
        """
        Returns one row per BOM component across all open production orders,
        including stock levels and shortfall per line.

        Corresponds to SQL Query 1 — Production Order BOM Requirements.
        """
        query, params = self._build_details_query(filters)
        rows = self._execute(query, params)
        return [self._map_detail_row(r) for r in rows]

    def get_sku_detail(self, doc_entry: int) -> List[Dict]:
        """
        Returns BOM component rows for a single production order.
        Uses the same detail query filtered to one DocEntry.
        """
        query, params = self._build_details_query({}, doc_entry=doc_entry)
        rows = self._execute(query, params)
        return [self._map_detail_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Query Builders
    # ------------------------------------------------------------------

    def _build_summary_query(self, filters: Dict[str, Any]):
        schema = self.connection.schema
        where_clauses, params = self._common_where(filters, schema, table_alias="T0")

        query = f"""
            SELECT
                T0."DocEntry"                       AS prod_order_entry,
                T0."DocNum"                         AS prod_order_num,
                T0."ItemCode"                       AS sku_code,
                IFNULL(T0."Dscription", '')         AS sku_name,
                T0."PlannedQty"                     AS planned_qty,
                T0."CmpltQty"                       AS completed_qty,
                T0."Status"                         AS status,
                T0."DueDate"                        AS due_date,
                T0."PostDate"                       AS post_date,
                T0."Priority"                       AS priority,
                T0."Warehouse"                      AS warehouse,
                COUNT(T1."LineNum")                 AS total_components,
                SUM(
                    CASE
                        WHEN (IFNULL(T2."OnHand", 0) - IFNULL(T2."IsCommited", 0))
                             < (IFNULL(T1."PlannedQty", 0) - IFNULL(T1."IssuedQty", 0))
                        THEN 1 ELSE 0
                    END
                )                                   AS components_with_shortfall,
                SUM(
                    IFNULL(T1."PlannedQty", 0) - IFNULL(T1."IssuedQty", 0)
                )                                   AS total_remaining_component_qty
            FROM "{schema}"."OWOR" T0
            INNER JOIN "{schema}"."WOR1" T1
                ON T0."DocEntry" = T1."DocEntry"
            LEFT JOIN "{schema}"."OITM" T2
                ON T1."ItemCode" = T2."ItemCode"
            WHERE {' AND '.join(where_clauses)}
            GROUP BY
                T0."DocEntry", T0."DocNum", T0."ItemCode", T0."Dscription",
                T0."PlannedQty", T0."CmpltQty", T0."Status",
                T0."DueDate", T0."PostDate", T0."Priority", T0."Warehouse"
            ORDER BY
                T0."DueDate" ASC,
                T0."DocNum" ASC
        """
        return query, params

    def _build_details_query(
        self, filters: Dict[str, Any], doc_entry: Optional[int] = None
    ):
        schema = self.connection.schema
        where_clauses, params = self._common_where(filters, schema, table_alias="T0")

        if doc_entry is not None:
            where_clauses.append('T0."DocEntry" = ?')
            params.append(doc_entry)

        query = f"""
            SELECT
                T0."DocEntry"                                               AS prod_order_entry,
                T0."DocNum"                                                 AS prod_order_num,
                T0."ItemCode"                                               AS sku_code,
                IFNULL(T0."Dscription", '')                                 AS sku_name,
                T0."PlannedQty"                                             AS sku_planned_qty,
                T0."CmpltQty"                                               AS sku_completed_qty,
                T0."Status"                                                 AS prod_order_status,
                T0."DueDate"                                                AS due_date,
                T0."PostDate"                                               AS post_date,
                T0."Warehouse"                                              AS prod_warehouse,
                T0."Priority"                                               AS priority,
                T1."LineNum"                                                AS component_line,
                T1."ItemCode"                                               AS component_code,
                IFNULL(T2."ItemName", T1."ItemCode")                        AS component_name,
                IFNULL(T1."PlannedQty", 0)                                 AS component_planned_qty,
                IFNULL(T1."IssuedQty", 0)                                  AS component_issued_qty,
                (IFNULL(T1."PlannedQty", 0) - IFNULL(T1."IssuedQty", 0))  AS component_remaining_qty,
                IFNULL(T1."Warehouse", '')                                  AS component_warehouse,
                IFNULL(T1."BaseQty", 0)                                    AS base_qty,
                IFNULL(T1."unitMsr", '')                                    AS uom,
                IFNULL(T2."OnHand", 0)                                     AS stock_on_hand,
                IFNULL(T2."IsCommited", 0)                                 AS stock_committed,
                IFNULL(T2."OnOrder", 0)                                    AS stock_on_order,
                (IFNULL(T2."OnHand", 0) - IFNULL(T2."IsCommited", 0))     AS net_available,
                IFNULL(T2."LeadTime", 0)                                   AS vendor_lead_time,
                IFNULL(T2."CardCode", '')                                   AS default_vendor
            FROM "{schema}"."OWOR" T0
            INNER JOIN "{schema}"."WOR1" T1
                ON T0."DocEntry" = T1."DocEntry"
            LEFT JOIN "{schema}"."OITM" T2
                ON T1."ItemCode" = T2."ItemCode"
            WHERE {' AND '.join(where_clauses)}
            ORDER BY
                T0."DueDate" ASC,
                T0."DocNum" ASC,
                T1."LineNum" ASC
        """
        return query, params

    # ------------------------------------------------------------------
    # WHERE Clause Helpers
    # ------------------------------------------------------------------

    def _common_where(
        self, filters: Dict[str, Any], schema: str, table_alias: str = "T0"
    ):
        """
        Builds common WHERE clauses + parameters list.
        Always enforces Status IN ('P','R'), ItemType = 'I', InvntItem = 'Y'.
        """
        clauses = []
        params = []

        # Status filter
        status = filters.get("status", "all")
        if status == "planned":
            clauses.append(f'{table_alias}."Status" = ?')
            params.append("P")
        elif status == "released":
            clauses.append(f'{table_alias}."Status" = ?')
            params.append("R")
        else:
            # Default: both planned and released
            clauses.append(f'{table_alias}."Status" IN (\'P\', \'R\')')

        # Date range filters
        if filters.get("due_date_from"):
            clauses.append(f'{table_alias}."DueDate" >= ?')
            params.append(filters["due_date_from"])

        if filters.get("due_date_to"):
            clauses.append(f'{table_alias}."DueDate" <= ?')
            params.append(filters["due_date_to"])

        # Warehouse filter
        if filters.get("warehouse"):
            clauses.append(f'{table_alias}."Warehouse" = ?')
            params.append(filters["warehouse"])

        # SKU filter
        if filters.get("sku"):
            clauses.append(f'{table_alias}."ItemCode" = ?')
            params.append(filters["sku"])

        # Always filter: inventory items only (ItemType 4 = Item in SAP B1 WOR1),
        # exclude resources (288) and non-inventory items
        clauses.append('T1."ItemType" = 4')
        clauses.append("T2.\"InvntItem\" = 'Y'")

        return clauses, params

    # ------------------------------------------------------------------
    # Row Mappers
    # ------------------------------------------------------------------

    def _map_summary_row(self, row) -> Dict:
        return {
            "prod_order_entry": int(row[0]),
            "prod_order_num": int(row[1]),
            "sku_code": row[2] or "",
            "sku_name": row[3] or "",
            "planned_qty": float(row[4] or 0),
            "completed_qty": float(row[5] or 0),
            "status": self._map_status(row[6]),
            "due_date": row[7].strftime("%Y-%m-%d") if row[7] else None,
            "post_date": row[8].strftime("%Y-%m-%d") if row[8] else None,
            "priority": int(row[9] or 0),
            "warehouse": row[10] or "",
            "total_components": int(row[11] or 0),
            "components_with_shortfall": int(row[12] or 0),
            "total_remaining_component_qty": float(row[13] or 0),
        }

    def _map_detail_row(self, row) -> Dict:
        component_remaining = float(row[16] or 0)
        net_available = float(row[23] or 0)
        shortfall = max(0.0, component_remaining - net_available)

        return {
            "prod_order_entry": int(row[0]),
            "prod_order_num": int(row[1]),
            "sku_code": row[2] or "",
            "sku_name": row[3] or "",
            "sku_planned_qty": float(row[4] or 0),
            "sku_completed_qty": float(row[5] or 0),
            "prod_order_status": self._map_status(row[6]),
            "due_date": row[7].strftime("%Y-%m-%d") if row[7] else None,
            "post_date": row[8].strftime("%Y-%m-%d") if row[8] else None,
            "prod_warehouse": row[9] or "",
            "priority": int(row[10] or 0),
            "component_line": int(row[11] or 0),
            "component_code": row[12] or "",
            "component_name": row[13] or "",
            "component_planned_qty": float(row[14] or 0),
            "component_issued_qty": float(row[15] or 0),
            "component_remaining_qty": component_remaining,
            "component_warehouse": row[17] or "",
            "base_qty": float(row[18] or 0),
            "uom": row[19] or "",
            "stock_on_hand": float(row[20] or 0),
            "stock_committed": float(row[21] or 0),
            "stock_on_order": float(row[22] or 0),
            "net_available": net_available,
            "vendor_lead_time": int(row[24] or 0),
            "default_vendor": row[25] or "",
            "shortfall_qty": shortfall,
        }

    # ------------------------------------------------------------------
    # Execution Helper
    # ------------------------------------------------------------------

    def _execute(self, query: str, params: List) -> List:
        conn = None
        cursor = None

        try:
            conn = self.connection.connect()
        except dbapi.Error as e:
            logger.error(f"SAP HANA connection failed: {e}")
            raise SAPConnectionError(
                "Unable to connect to SAP HANA. Please try again later."
            ) from e

        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

        except dbapi.ProgrammingError as e:
            logger.error(f"SAP HANA query error in plan dashboard: {e}")
            raise SAPDataError(
                "Failed to retrieve plan dashboard data from SAP. Invalid query."
            ) from e
        except dbapi.Error as e:
            logger.error(f"SAP HANA data error in plan dashboard: {e}")
            raise SAPDataError(
                "Failed to retrieve plan dashboard data from SAP. Please try again."
            ) from e
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------

    @staticmethod
    def _map_status(raw: str) -> str:
        mapping = {"P": "planned", "R": "released", "L": "closed", "C": "cancelled"}
        return mapping.get(raw, raw or "")
