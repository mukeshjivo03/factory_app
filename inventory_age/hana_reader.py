"""
inventory_age/hana_reader.py

Calls SAP HANA stored procedure SP_InventoryAgeValue to retrieve
inventory age and valuation data for the current company schema.
"""

import logging
from typing import Dict, List

from hdbcli import dbapi

from sap_client.hana.connection import HanaConnection
from sap_client.exceptions import SAPConnectionError, SAPDataError

logger = logging.getLogger(__name__)


class HanaInventoryAgeReader:
    """
    Reads inventory age & value data by calling SP_InventoryAgeValue.

    The stored procedure accepts no parameters and returns one row per
    item-warehouse combination with columns:
        ItemCode, ItemName, U_IsLitre, ItemGroup, U_Unit, U_Variety,
        U_SKU, U_Sub_Group, WhsCode, OnHand, Litres, InStockValue,
        CalcPrice, EffectiveDate, DaysAge
    """

    def __init__(self, context):
        self.connection = HanaConnection(context.hana)

    def get_inventory_age(self) -> List[Dict]:
        """Call SP_InventoryAgeValue and return mapped rows."""
        rows = self._execute()
        return [self._map_row(r) for r in rows]

    def _map_row(self, row) -> Dict:
        return {
            "item_code": row[0] or "",
            "item_name": row[1] or "",
            "is_litre": (row[2] or "N") == "Y",
            "item_group": row[3] or "",
            "unit": row[4] or "",
            "variety": row[5] or "",
            "sku": row[6] or "",
            "sub_group": row[7] or "",
            "warehouse": row[8] or "",
            "on_hand": float(row[9] or 0),
            "litres": float(row[10] or 0),
            "in_stock_value": float(row[11] or 0),
            "calc_price": float(row[12] or 0),
            "effective_date": str(row[13]) if row[13] else None,
            "days_age": int(row[14] or 0),
        }

    def _execute(self) -> List:
        schema = self.connection.schema
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
            cursor.execute(f'CALL "{schema}"."SP_InventoryAgeValue"()')
            return cursor.fetchall()

        except dbapi.ProgrammingError as e:
            logger.error(f"SAP HANA query error in inventory age: {e}")
            raise SAPDataError(
                f"Inventory age SP error: {e}"
            ) from e
        except dbapi.Error as e:
            logger.error(f"SAP HANA data error in inventory age: {e}")
            raise SAPDataError(
                f"Inventory age HANA error: {e}"
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
