from dataclasses import dataclass
from typing import List, Optional


@dataclass
class POItemDTO:
    po_item_code: str
    item_name: str
    ordered_qty: float
    received_qty: float
    remaining_qty: float
    uom: str
    rate: float = 0.0
    line_num: int = 0
    tax_code: str = ""
    warehouse_code: str = ""
    account_code: str = ""


@dataclass
class PODTO:
    po_number: str
    supplier_code: str
    supplier_name: str
    items: List[POItemDTO]
    doc_entry: int = 0
    branch_id: Optional[int] = None
    vendor_ref: str = ""


@dataclass
class GRPOLineDTO:
    """GRPO Document Line Item"""
    item_code: str
    quantity: float
    tax_code: Optional[str] = None
    unit_price: Optional[float] = None
    base_entry: Optional[int] = None  # PO DocEntry for PO-based GRPO
    base_line: Optional[int] = None   # PO line number
    base_type: Optional[int] = None   # 22 for Purchase Order
    warehouse_code: Optional[str] = None


@dataclass
class GRPORequestDTO:
    """GRPO Document Request"""
    card_code: str
    document_lines: List[GRPOLineDTO]
    doc_date: Optional[str] = None
    doc_due_date: Optional[str] = None
    comments: Optional[str] = None


@dataclass
class GRPOResponseDTO:
    """GRPO Document Response from SAP"""
    doc_entry: int
    doc_num: int
    card_code: str
    card_name: Optional[str] = None
    doc_date: Optional[str] = None
    doc_total: Optional[float] = None


@dataclass
class WarehouseDTO:
    """Active Warehouse from SAP"""
    warehouse_code: str
    warehouse_name: str


@dataclass
class VendorDTO:
    """Active Vendor from SAP"""
    vendor_code: str
    vendor_name: str
