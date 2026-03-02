# GRPO API Reference & Changes

## Summary of All Changes

### What Changed
The GRPO posting flow was updated to support **PO-linked GRPO** (BaseEntry/BaseLine/BaseType), additional line-level fields, vendor references, extra charges, structured comments, and **file attachments with SAP sync**. Address handling was removed — SAP inherits the address automatically from the linked PO.

### Files Modified

| File | What Changed |
|------|-------------|
| `sap_client/hana/po_reader.py` | Expanded HANA query to also fetch `TaxCode`, `WhsCode`, `AcctCode` from POR1 and `BPLId`, `NumAtCard` from OPOR |
| `sap_client/dtos.py` | Added `tax_code`, `warehouse_code`, `account_code` to `POItemDTO`; added `branch_id`, `vendor_ref` to `PODTO` |
| `sap_client/service_layer/attachment_writer.py` | **New** — SAP Attachments2 upload + link to GRPO document via PATCH |
| `sap_client/client.py` | Added `upload_attachment()` and `link_attachment_to_grpo()` methods |
| `raw_material_gatein/models/po_receipt.py` | Added `sap_doc_entry`, `branch_id`, `vendor_ref` fields |
| `raw_material_gatein/models/po_item_receipt.py` | Added `sap_line_num`, `unit_price`, `tax_code`, `warehouse_code`, `gl_account` fields |
| `raw_material_gatein/views.py` | Updated `ReceivePOAPI` to extract and store all PO header/line fields during PO receive |
| `grpo/models.py` | Added `base_entry`/`base_line` to `GRPOLinePosting`; added `SAPAttachmentStatus` + `GRPOAttachment` model |
| `grpo/serializers.py` | Added pre-fill fields, `GRPOItemInputSerializer`, `ExtraChargeInputSerializer`, `GRPOAttachmentSerializer`, `GRPOAttachmentUploadSerializer`; updated `GRPOPostingSerializer` with attachments |
| `grpo/services.py` | Preview returns all PO details; PO linking logic; added `upload_grpo_attachment()`, `retry_attachment_upload()` |
| `grpo/views.py` | Updated `PostGRPOAPI`; added `GRPOAttachmentListCreateAPI`, `GRPOAttachmentDeleteAPI`, `GRPOAttachmentRetryAPI` |
| `grpo/urls.py` | Added 3 new attachment URL patterns |
| `grpo/permissions.py` | Added `CanManageGRPOAttachments` permission |
| `grpo/admin.py` | Added `GRPOAttachmentInline` to `GRPOPostingAdmin` |
| `grpo/tests.py` | 37 tests covering all functionality including attachments |
| `raw_material_gatein/migrations/0009_add_sap_po_linking_fields.py` | Migration for sap_doc_entry, sap_line_num |
| `raw_material_gatein/migrations/0010_add_po_detail_fields.py` | Migration for unit_price, tax_code, warehouse_code, gl_account, branch_id, vendor_ref |
| `grpo/migrations/0008_grpoattachment.py` | Migration for GRPOAttachment model |
| `grpo/migrations/0009_update_grpo_group_attachments.py` | Data migration for attachment permissions |

---

## API Endpoints

### Base URL: `/api/grpo/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/grpo/pending/` | List gate entries pending GRPO posting |
| GET | `/api/grpo/preview/<vehicle_entry_id>/` | Preview GRPO data for a gate entry |
| POST | `/api/grpo/post/` | Post GRPO to SAP |
| GET | `/api/grpo/history/` | GRPO posting history |
| GET | `/api/grpo/<posting_id>/` | GRPO posting detail |
| GET | `/api/grpo/<posting_id>/attachments/` | List attachments for a GRPO posting |
| POST | `/api/grpo/<posting_id>/attachments/` | Upload attachment (multipart/form-data) |
| DELETE | `/api/grpo/<posting_id>/attachments/<attachment_id>/` | Delete an attachment |
| POST | `/api/grpo/<posting_id>/attachments/<attachment_id>/retry/` | Retry failed SAP upload |

**All endpoints require:**
- `Authorization: Token <token>` header
- `X-Company-Code: <code>` header (company context)

---

## 1. GET /api/grpo/pending/

Lists all completed gate entries that have POs pending GRPO posting.

### Request
```
GET /api/grpo/pending/
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (200 OK)
```json
[
  {
    "vehicle_entry_id": 45,
    "entry_no": "GE-2026-0045",
    "status": "COMPLETED",
    "entry_time": "2026-02-28T10:30:00Z",
    "total_po_count": 3,
    "posted_po_count": 1,
    "pending_po_count": 2,
    "is_fully_posted": false
  },
  {
    "vehicle_entry_id": 42,
    "entry_no": "GE-2026-0042",
    "status": "QC_COMPLETED",
    "entry_time": "2026-02-27T14:15:00Z",
    "total_po_count": 1,
    "posted_po_count": 0,
    "pending_po_count": 1,
    "is_fully_posted": false
  }
]
```

**Notes:**
- Only entries with `status = COMPLETED` or `QC_COMPLETED` appear here
- Only entries with `pending_po_count > 0` are returned
- Entries where all POs are already posted are excluded

---

## 2. GET /api/grpo/preview/<vehicle_entry_id>/

Returns all data needed to post GRPO for a specific gate entry. Shows PO details, items, QC status, and accepted quantities.

### Request
```
GET /api/grpo/preview/45/
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (200 OK)
```json
[
  {
    "vehicle_entry_id": 45,
    "entry_no": "GE-2026-0045",
    "entry_status": "COMPLETED",
    "is_ready_for_grpo": true,
    "po_receipt_id": 101,
    "po_number": "PO-2026-0123",
    "supplier_code": "V10001",
    "supplier_name": "ABC Suppliers Pvt Ltd",
    "sap_doc_entry": 12345,
    "branch_id": 1,
    "vendor_ref": "VINV-2026-789",
    "invoice_no": "INV-9876",
    "invoice_date": "2026-02-25",
    "challan_no": "CH-5432",
    "items": [
      {
        "po_item_receipt_id": 201,
        "item_code": "RM-STEEL-01",
        "item_name": "MS Steel Rod 12mm",
        "ordered_qty": "1000.000",
        "received_qty": "980.000",
        "accepted_qty": "950.000",
        "rejected_qty": "30.000",
        "uom": "KG",
        "qc_status": "ACCEPTED",
        "unit_price": "85.500000",
        "tax_code": "GST18",
        "warehouse_code": "WH-01",
        "gl_account": "40001001",
        "sap_line_num": 0
      },
      {
        "po_item_receipt_id": 202,
        "item_code": "RM-STEEL-02",
        "item_name": "MS Steel Rod 16mm",
        "ordered_qty": "500.000",
        "received_qty": "500.000",
        "accepted_qty": "500.000",
        "rejected_qty": "0.000",
        "uom": "KG",
        "qc_status": "ACCEPTED",
        "unit_price": "92.000000",
        "tax_code": "GST18",
        "warehouse_code": "WH-01",
        "gl_account": "40001001",
        "sap_line_num": 1
      }
    ],
    "grpo_status": null,
    "sap_doc_num": null
  },
  {
    "vehicle_entry_id": 45,
    "entry_no": "GE-2026-0045",
    "entry_status": "COMPLETED",
    "is_ready_for_grpo": true,
    "po_receipt_id": 102,
    "po_number": "PO-2026-0124",
    "supplier_code": "V10001",
    "supplier_name": "ABC Suppliers Pvt Ltd",
    "sap_doc_entry": 12346,
    "branch_id": 1,
    "vendor_ref": "",
    "invoice_no": "",
    "invoice_date": null,
    "challan_no": "",
    "items": [
      {
        "po_item_receipt_id": 203,
        "item_code": "RM-CEMENT-01",
        "item_name": "OPC Cement 53 Grade",
        "ordered_qty": "200.000",
        "received_qty": "200.000",
        "accepted_qty": "200.000",
        "rejected_qty": "0.000",
        "uom": "BAG",
        "qc_status": "ACCEPTED",
        "unit_price": "350.000000",
        "tax_code": "GST28",
        "warehouse_code": "WH-02",
        "gl_account": "40002001",
        "sap_line_num": 0
      }
    ],
    "grpo_status": "POSTED",
    "sap_doc_num": 50001
  }
]
```

**Notes:**
- `sap_doc_entry` is the SAP PO DocEntry — needed for PO linking in GRPO
- `branch_id` is pre-filled from the PO (OPOR.BPLId) — use directly in the POST request
- `vendor_ref` is pre-filled from the PO (OPOR.NumAtCard) — use directly in the POST request
- Per-item fields `unit_price`, `tax_code`, `warehouse_code`, `gl_account` are all pre-filled from the PO — the frontend can show these to the user and pass them directly in the POST request
- `grpo_status = null` means not yet posted; `"POSTED"` means already done
- `qc_status` values: `ACCEPTED`, `REJECTED`, `PARTIALLY_ACCEPTED`, `NO_ARRIVAL_SLIP`, `ARRIVAL_SLIP_PENDING`, `INSPECTION_PENDING`
- `is_ready_for_grpo` is `true` only when gate entry status is `COMPLETED` or `QC_COMPLETED`

### Pre-filled Fields Mapping (Preview to Post)

The preview returns PO details that can be used directly in the GRPO POST request. Here's the mapping:

| Preview Field (from GET) | POST Field (to send) | Level |
|--------------------------|---------------------|-------|
| `branch_id` | `branch_id` | Header |
| `vendor_ref` | `vendor_ref` | Header |
| Per-item `warehouse_code` | `warehouse_code` | Header (same for all) |
| Per-item `unit_price` | items[].`unit_price` | Line |
| Per-item `tax_code` | items[].`tax_code` | Line |
| Per-item `gl_account` | items[].`gl_account` | Line |

**User only needs to fill:** `accepted_qty` per item (and optionally `variety`, `comments`, `extra_charges`)

### Response (404 Not Found)
```json
{
  "detail": "Vehicle entry 999 not found"
}
```

---

## 3. POST /api/grpo/post/

Posts GRPO to SAP for a specific PO receipt. This is the main posting endpoint.

### Request — Minimum Required Fields
```json
{
  "vehicle_entry_id": 45,
  "po_receipt_id": 101,
  "branch_id": 1,
  "items": [
    {
      "po_item_receipt_id": 201,
      "accepted_qty": 950
    },
    {
      "po_item_receipt_id": 202,
      "accepted_qty": 500
    }
  ]
}
```

### Request — Full Payload (All Optional Fields)
```json
{
  "vehicle_entry_id": 45,
  "po_receipt_id": 101,
  "branch_id": 1,
  "warehouse_code": "WH-01",
  "comments": "Material quality verified by QC team",
  "vendor_ref": "VINV-2026-789",
  "items": [
    {
      "po_item_receipt_id": 201,
      "accepted_qty": 950,
      "unit_price": 85.50,
      "tax_code": "GST18",
      "gl_account": "40001001",
      "variety": "TMT-500D"
    },
    {
      "po_item_receipt_id": 202,
      "accepted_qty": 500,
      "unit_price": 92.00,
      "tax_code": "GST18",
      "gl_account": "40001001",
      "variety": "TMT-500D"
    }
  ],
  "extra_charges": [
    {
      "expense_code": 1,
      "amount": 5000.00,
      "remarks": "Freight charges",
      "tax_code": "GST18"
    },
    {
      "expense_code": 2,
      "amount": 1500.00,
      "remarks": "Loading/Unloading",
      "tax_code": "GST18"
    }
  ]
}
```

### Field Reference

#### Header Fields (Required)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vehicle_entry_id` | int | Yes | ID of the gate entry |
| `po_receipt_id` | int | Yes | ID of the PO receipt to post |
| `branch_id` | int | Yes | SAP Branch/Business Place ID (BPL_IDAssignedToInvoice) |
| `items` | array | Yes | At least one item required |

#### Header Fields (Optional)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `warehouse_code` | string | No | SAP Warehouse Code (applied to all lines if provided) |
| `comments` | string | No | User remarks — appended to auto-generated structured comment |
| `vendor_ref` | string | No | Vendor reference / invoice number (maps to `NumAtCard` in SAP) |
| `extra_charges` | array | No | Additional expenses (freight, handling, etc.) |

#### Item Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `po_item_receipt_id` | int | Yes | ID of the POItemReceipt |
| `accepted_qty` | decimal | Yes | Quantity accepted for GRPO (cannot exceed `received_qty`) |
| `unit_price` | decimal | No | Unit price per item (maps to `UnitPrice` in SAP) |
| `tax_code` | string | No | SAP Tax Code, e.g. `GST18`, `IGST18` (maps to `TaxCode`) |
| `gl_account` | string | No | G/L Account code (maps to `AccountCode` in SAP) |
| `variety` | string | No | Item variety (maps to SAP UDF `U_Variety`) |

#### Extra Charge Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `expense_code` | int | Yes | SAP Expense Code (from Additional Expenses setup) |
| `amount` | decimal | Yes | Total amount for this charge |
| `remarks` | string | No | Description (e.g. "Freight", "Handling") |
| `tax_code` | string | No | Tax code for this charge |

### SAP Payload Generated (What Gets Sent to SAP)

The API automatically builds the following SAP Service Layer payload:

```json
{
  "CardCode": "V10001",
  "BPL_IDAssignedToInvoice": 1,
  "NumAtCard": "VINV-2026-789",
  "Comments": "App: FactoryApp v2 | User: John Doe (john.doe) | PO: PO-2026-0123 | Gate Entry: GE-2026-0045 | Material quality verified by QC team",
  "DocumentLines": [
    {
      "ItemCode": "RM-STEEL-01",
      "Quantity": "950.000",
      "BaseEntry": 12345,
      "BaseLine": 0,
      "BaseType": 22,
      "WarehouseCode": "WH-01",
      "UnitPrice": 85.5,
      "TaxCode": "GST18",
      "AccountCode": "40001001",
      "U_Variety": "TMT-500D"
    },
    {
      "ItemCode": "RM-STEEL-02",
      "Quantity": "500.000",
      "BaseEntry": 12345,
      "BaseLine": 1,
      "BaseType": 22,
      "WarehouseCode": "WH-01",
      "UnitPrice": 92.0,
      "TaxCode": "GST18",
      "AccountCode": "40001001",
      "U_Variety": "TMT-500D"
    }
  ],
  "DocumentAdditionalExpenses": [
    {
      "ExpenseCode": 1,
      "LineTotal": 5000.0,
      "Remarks": "Freight charges",
      "TaxCode": "GST18"
    },
    {
      "ExpenseCode": 2,
      "LineTotal": 1500.0,
      "Remarks": "Loading/Unloading",
      "TaxCode": "GST18"
    }
  ]
}
```

### Response (201 Created)
```json
{
  "success": true,
  "grpo_posting_id": 15,
  "sap_doc_entry": 67890,
  "sap_doc_num": 50002,
  "sap_doc_total": "86775.00",
  "message": "GRPO posted successfully. SAP Doc Num: 50002"
}
```

### Error Responses

**400 Bad Request — Validation Error**
```json
{
  "detail": "Invalid request data",
  "errors": {
    "branch_id": ["This field is required."],
    "items": ["At least one item with accepted quantity is required"]
  }
}
```

**400 Bad Request — Already Posted**
```json
{
  "detail": "GRPO already posted for PO PO-2026-0123. SAP Doc Num: 50001"
}
```

**400 Bad Request — Accepted Qty Exceeds Received**
```json
{
  "detail": "Accepted qty (1100.000) cannot exceed received qty (980.000) for item MS Steel Rod 12mm"
}
```

**400 Bad Request — Gate Entry Not Completed**
```json
{
  "detail": "Gate entry is not completed. Current status: IN_PROGRESS"
}
```

**400 Bad Request — SAP Validation Error**
```json
{
  "detail": "SAP validation error: Document lines total does not match header total"
}
```

**502 Bad Gateway — SAP Data Error**
```json
{
  "detail": "SAP error: Invalid CardCode V10001"
}
```

**503 Service Unavailable — SAP Down**
```json
{
  "detail": "SAP system is currently unavailable. Please try again later."
}
```

---

## 4. GET /api/grpo/history/

Returns all GRPO posting history. Can be filtered by vehicle entry.

### Request
```
GET /api/grpo/history/
GET /api/grpo/history/?vehicle_entry_id=45
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (200 OK)
```json
[
  {
    "id": 15,
    "vehicle_entry": 45,
    "entry_no": "GE-2026-0045",
    "po_receipt": 101,
    "po_number": "PO-2026-0123",
    "sap_doc_entry": 67890,
    "sap_doc_num": 50002,
    "sap_doc_total": "86775.00",
    "status": "POSTED",
    "error_message": null,
    "posted_at": "2026-02-28T11:45:00Z",
    "posted_by": 5,
    "created_at": "2026-02-28T11:44:55Z",
    "lines": [
      {
        "id": 30,
        "item_code": "RM-STEEL-01",
        "item_name": "MS Steel Rod 12mm",
        "quantity_posted": "950.000",
        "base_entry": 12345,
        "base_line": 0
      },
      {
        "id": 31,
        "item_code": "RM-STEEL-02",
        "item_name": "MS Steel Rod 16mm",
        "quantity_posted": "500.000",
        "base_entry": 12345,
        "base_line": 1
      }
    ],
    "attachments": [
      {
        "id": 1,
        "file": "/media/grpo_attachments/invoice_abc123.pdf",
        "original_filename": "invoice.pdf",
        "sap_attachment_status": "LINKED",
        "sap_absolute_entry": 456,
        "sap_error_message": null,
        "uploaded_at": "2026-02-28T12:00:00Z",
        "uploaded_by": 5
      }
    ]
  }
]
```

---

## 5. GET /api/grpo/<posting_id>/

Returns details of a specific GRPO posting.

### Request
```
GET /api/grpo/15/
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (200 OK)
Same structure as a single item in the history response above (includes `lines` and `attachments`).

### Response (404 Not Found)
```json
{
  "detail": "GRPO posting not found"
}
```

---

## 6. POST /api/grpo/<posting_id>/attachments/

Upload an attachment for a GRPO posting. The file is saved locally, then uploaded to SAP Attachments2 endpoint, and linked to the GRPO document.

### Request
```
POST /api/grpo/15/attachments/
Authorization: Token abc123
X-Company-Code: COMP01
Content-Type: multipart/form-data

file: <binary file data>
```

### Response (201 Created)
```json
{
  "id": 1,
  "file": "/media/grpo_attachments/invoice_abc123.pdf",
  "original_filename": "invoice.pdf",
  "sap_attachment_status": "LINKED",
  "sap_absolute_entry": 456,
  "sap_error_message": null,
  "uploaded_at": "2026-02-28T12:00:00Z",
  "uploaded_by": 5
}
```

**If SAP upload fails**, the file is still saved locally and the response will show:
```json
{
  "id": 1,
  "file": "/media/grpo_attachments/invoice_abc123.pdf",
  "original_filename": "invoice.pdf",
  "sap_attachment_status": "FAILED",
  "sap_absolute_entry": null,
  "sap_error_message": "Unable to connect to SAP Service Layer",
  "uploaded_at": "2026-02-28T12:00:00Z",
  "uploaded_by": 5
}
```

### Error Responses

**400 Bad Request — GRPO Not Posted**
```json
{
  "detail": "Cannot attach files to GRPO with status 'PENDING'. Only POSTED GRPOs accept attachments."
}
```

**400 Bad Request — No File Provided**
```json
{
  "detail": "Invalid file upload",
  "errors": {"file": ["No file was submitted."]}
}
```

---

## 7. GET /api/grpo/<posting_id>/attachments/

List all attachments for a GRPO posting.

### Request
```
GET /api/grpo/15/attachments/
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (200 OK)
```json
[
  {
    "id": 1,
    "file": "/media/grpo_attachments/invoice_abc123.pdf",
    "original_filename": "invoice.pdf",
    "sap_attachment_status": "LINKED",
    "sap_absolute_entry": 456,
    "sap_error_message": null,
    "uploaded_at": "2026-02-28T12:00:00Z",
    "uploaded_by": 5
  },
  {
    "id": 2,
    "file": "/media/grpo_attachments/challan_def456.jpg",
    "original_filename": "challan.jpg",
    "sap_attachment_status": "FAILED",
    "sap_absolute_entry": null,
    "sap_error_message": "SAP Service Layer connection timeout",
    "uploaded_at": "2026-02-28T12:05:00Z",
    "uploaded_by": 5
  }
]
```

---

## 8. DELETE /api/grpo/<posting_id>/attachments/<attachment_id>/

Delete an attachment. Removes both the database record and the physical file.

### Request
```
DELETE /api/grpo/15/attachments/2/
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (204 No Content)
No body returned.

### Response (404 Not Found)
```json
{
  "detail": "Attachment not found"
}
```

---

## 9. POST /api/grpo/<posting_id>/attachments/<attachment_id>/retry/

Retry uploading a FAILED attachment to SAP. If the file was already uploaded to SAP (has `sap_absolute_entry`) but linking failed, it will skip re-upload and only retry the link.

### Request
```
POST /api/grpo/15/attachments/2/retry/
Authorization: Token abc123
X-Company-Code: COMP01
```

### Response (200 OK)
```json
{
  "id": 2,
  "file": "/media/grpo_attachments/challan_def456.jpg",
  "original_filename": "challan.jpg",
  "sap_attachment_status": "LINKED",
  "sap_absolute_entry": 789,
  "sap_error_message": null,
  "uploaded_at": "2026-02-28T12:05:00Z",
  "uploaded_by": 5
}
```

### Error Responses

**400 Bad Request — Already Linked**
```json
{
  "detail": "Attachment is already 'LINKED'. Only PENDING or FAILED attachments can be retried."
}
```

---

## Important Things to Know

### 1. PO Linking (BaseEntry / BaseLine / BaseType)
- GRPO is now **linked to the original Purchase Order** in SAP
- `BaseEntry` = SAP PO DocEntry (from `OPOR.DocEntry`)
- `BaseLine` = SAP PO Line Number (from `POR1.LineNum`)
- `BaseType` = `22` (SAP constant for Purchase Order)
- This linking is **automatic** — the system stores `sap_doc_entry` and `sap_line_num` during PO receive and uses them during GRPO posting
- If `sap_doc_entry` or `sap_line_num` is missing (null), the GRPO will post as a **standalone document** (no PO link)

### 2. Address Not Needed
- When GRPO is linked to a PO (BaseEntry/BaseLine), SAP **automatically inherits** the shipping address from the Purchase Order
- No address fields are sent in the GRPO payload
- This simplifies the API and avoids address format issues

### 3. Structured Comments (Auto-Generated)
- The `Comments` field in SAP is **auto-built** by the system in this format:
  ```
  App: FactoryApp v2 | User: John Doe (john.doe) | PO: PO-2026-0123 | Gate Entry: GE-2026-0045
  ```
- If the user provides a `comments` field in the request, it is **appended** to the auto-generated comment:
  ```
  App: FactoryApp v2 | User: John Doe (john.doe) | PO: PO-2026-0123 | Gate Entry: GE-2026-0045 | Material quality verified by QC team
  ```

### 4. Vendor Reference (NumAtCard)
- The `vendor_ref` field maps to SAP's `NumAtCard`
- Typically used for the vendor's invoice number or delivery challan number
- Optional — only sent to SAP when provided

### 5. U_Variety (SAP User Defined Field)
- `variety` on each item maps to SAP UDF `U_Variety`
- This field must be configured in SAP B1 before use
- If the UDF does not exist in SAP, posting will fail with a SAP validation error

### 6. Extra Charges (DocumentAdditionalExpenses)
- Used for freight, handling, loading/unloading, and other incidental costs
- `expense_code` must match the SAP Additional Expenses setup
- Each charge can have its own `tax_code`
- These charges are added to the GRPO document total

### 7. Accepted Quantity Updates
- When you call POST `/api/grpo/post/`, the system **updates** `accepted_qty` and `rejected_qty` on `POItemReceipt` based on the `accepted_qty` you send
- `rejected_qty` = `received_qty` - `accepted_qty` (calculated automatically)
- `accepted_qty` cannot exceed `received_qty`

### 8. Duplicate Posting Prevention
- The system prevents duplicate GRPO posting for the same PO receipt
- If a GRPO with status `POSTED` already exists for a `(vehicle_entry, po_receipt)` pair, the API returns 400
- The `unique_together` constraint on the model enforces this at the database level

### 9. Items with Zero Accepted Qty are Skipped
- If an item has `accepted_qty = 0`, it is excluded from the SAP payload
- If ALL items have zero accepted qty, the posting fails with: `"No accepted quantities to post for this PO"`

### 10. GRPO Status Values
| Status | Meaning |
|--------|---------|
| `PENDING` | Record created, SAP call not yet made |
| `POSTED` | Successfully posted to SAP |
| `FAILED` | SAP call failed (error_message has details) |
| `PARTIALLY_POSTED` | Reserved for future use |

### 11. Required Permissions

| Endpoint | Permission |
|----------|-----------|
| GET /pending/ | `can_view_pending_grpo` |
| GET /preview/ | `can_preview_grpo` |
| POST /post/ | `add_grpoposting` (Django default) |
| GET /history/ | `can_view_grpo_history` |
| GET /detail/ | `view_grpoposting` (Django default) |

### 12. Preview Pre-fills Everything from PO
- The preview API now returns **all PO details** so the frontend can pre-fill the posting form
- **Header-level**: `branch_id`, `vendor_ref` come pre-filled from the PO
- **Item-level**: `unit_price`, `tax_code`, `warehouse_code`, `gl_account` come pre-filled per item
- The user only needs to confirm/edit `accepted_qty` per item and optionally add `variety`, `comments`, or `extra_charges`
- These fields are stored during PO receive (from SAP HANA) and returned at preview time — no extra SAP call needed

### 13. Data Flow (End to End)

```
1. Gate Entry Created (driver_management)
         |
2. PO Received (raw_material_gatein/ReceivePOAPI)
   - Fetches PO from SAP HANA (OPOR + POR1)
   - Stores on POReceipt: sap_doc_entry, branch_id, vendor_ref
   - Stores on POItemReceipt: sap_line_num, unit_price, tax_code, warehouse_code, gl_account
         |
3. QC Inspection (quality_control)
   - Sets accepted_qty, rejected_qty
         |
4. Gate Entry Completed (status = COMPLETED / QC_COMPLETED)
         |
5. GRPO Preview (grpo/GRPOPreviewAPI)
   - Returns ALL PO details (pre-filled for the posting form)
   - Shows QC status, quantities, and which POs are already posted
   - Frontend uses this to pre-fill the GRPO posting form
         |
6. GRPO Post (grpo/PostGRPOAPI)
   - User confirms/edits accepted_qty and optionally adds variety, comments, extra_charges
   - Builds SAP payload with PO linking (BaseEntry/BaseLine/BaseType)
   - Posts to SAP Service Layer: POST /b1s/v2/PurchaseDeliveryNotes
   - Records result in GRPOPosting + GRPOLinePosting
```

### 14. SAP Service Layer Endpoint
- **URL:** `POST /b1s/v2/PurchaseDeliveryNotes`
- This is the SAP B1 Service Layer endpoint for GRPO (Goods Receipt PO)
- The SAP client handles login/session management automatically

### 15. SAP HANA Fields Fetched During PO Receive

| HANA Column | Stored In | Field Name | Used For |
|-------------|-----------|------------|----------|
| `OPOR.DocEntry` | POReceipt | `sap_doc_entry` | BaseEntry in GRPO |
| `OPOR.BPLId` | POReceipt | `branch_id` | BPL_IDAssignedToInvoice |
| `OPOR.NumAtCard` | POReceipt | `vendor_ref` | NumAtCard |
| `POR1.LineNum` | POItemReceipt | `sap_line_num` | BaseLine in GRPO |
| `POR1.Price` | POItemReceipt | `unit_price` | UnitPrice |
| `POR1.TaxCode` | POItemReceipt | `tax_code` | TaxCode |
| `POR1.WhsCode` | POItemReceipt | `warehouse_code` | WarehouseCode |
| `POR1.AcctCode` | POItemReceipt | `gl_account` | AccountCode |

### 16. Database Models

**POReceipt** (raw_material_gatein)
- `sap_doc_entry` — SAP PO DocEntry (integer, nullable)
- `branch_id` — SAP Branch/Business Place ID (integer, nullable)
- `vendor_ref` — Vendor reference from PO (string)

**POItemReceipt** (raw_material_gatein)
- `sap_line_num` — SAP PO LineNum (integer, nullable)
- `unit_price` — Unit price from PO (decimal, nullable)
- `tax_code` — Tax code from PO (string)
- `warehouse_code` — Warehouse code from PO (string)
- `gl_account` — G/L Account from PO (string)

**GRPOPosting** (grpo)
- `vehicle_entry` — FK to VehicleEntry
- `po_receipt` — FK to POReceipt
- `sap_doc_entry` — SAP GRPO DocEntry (response)
- `sap_doc_num` — SAP GRPO DocNum (response)
- `sap_doc_total` — Document total from SAP
- `status` — PENDING / POSTED / FAILED
- `error_message` — Error details if failed
- `posted_at` — Timestamp
- `posted_by` — FK to User

**GRPOLinePosting** (grpo)
- `grpo_posting` — FK to GRPOPosting
- `po_item_receipt` — FK to POItemReceipt
- `quantity_posted` — Decimal
- `base_entry` — PO DocEntry used for linking
- `base_line` — PO LineNum used for linking
