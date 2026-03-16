import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SAPWriteError(Exception):
    pass


class GoodsReceiptWriter:
    """Posts production goods receipts to SAP B1 Service Layer."""

    def __init__(self, company_code: str):
        self.company_code = company_code
        from sap_client.client import SAPClient
        try:
            self.client = SAPClient(company_code=company_code)
        except Exception as e:
            raise SAPWriteError(f"Failed to initialize SAP client: {e}")

    def post_goods_receipt(
        self,
        doc_entry: int,
        item_code: str,
        warehouse: str,
        qty: float,
        posting_date,
    ) -> int:
        """
        Post a production goods receipt to SAP B1.
        Returns the DocEntry of the created GR document.
        """
        sl_config = self.client.context.service_layer
        base_url = sl_config['base_url']

        # Authenticate
        session = requests.Session()
        login_resp = session.post(
            f"{base_url}/b1s/v2/Login",
            json={
                "CompanyDB": sl_config['company_db'],
                "UserName": sl_config['username'],
                "Password": sl_config['password'],
            },
            timeout=10,
            verify=False,
        )
        if not login_resp.ok:
            raise SAPWriteError(f"SAP Service Layer login failed: {login_resp.text}")

        payload = {
            "DocDate": posting_date.isoformat() if hasattr(posting_date, 'isoformat') else str(posting_date),
            "Comments": f"Production Execution — DocEntry {doc_entry}",
            "DocumentLines": [{
                "ItemCode": item_code,
                "Quantity": float(qty),
                "WarehouseCode": warehouse,
                "BaseType": 202,
                "BaseEntry": doc_entry,
                "BaseLine": 0,
            }],
        }

        response = session.post(
            f"{base_url}/b1s/v2/InventoryGenEntries",
            json=payload,
            timeout=30,
            verify=False,
        )

        if not response.ok:
            error_msg = self._extract_error(response)
            raise SAPWriteError(f"Failed to post GR to SAP: {error_msg}")

        result = response.json()
        return result.get('DocEntry')

    @staticmethod
    def _extract_error(response: requests.Response) -> str:
        try:
            data = response.json()
            return data.get('error', {}).get('message', {}).get('value', response.text)
        except Exception:
            return response.text
