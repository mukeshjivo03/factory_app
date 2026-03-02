# GRPO Posting - Complete API Documentation

## Table of Contents
1. [Overview](#1-overview)
2. [API Endpoints](#2-api-endpoints)
3. [POST /api/grpo/post/ - Full Payload Reference](#3-post-apigrpopost---full-payload-reference)
4. [SAP Payload (What Gets Sent to SAP)](#4-sap-payload-what-gets-sent-to-sap)
5. [PO Linking (BaseEntry / BaseLine / BaseType)](#5-po-linking-baseentry--baseline--basetype)
6. [Line-Level Fields (Per Item)](#6-line-level-fields-per-item)
7. [Extra Charges (DocumentAdditionalExpenses)](#7-extra-charges-documentadditionalexpenses)
8. [Structured Comments](#8-structured-comments)
9. [Vendor Reference (NumAtCard)](#9-vendor-reference-numatcard)
10. [SAP Field Mapping (Complete)](#10-sap-field-mapping-complete)
11. [Error Handling](#11-error-handling)
12. [End-to-End Flow](#12-end-to-end-flow)
13. [Key Files](#13-key-files)
14. [Important Notes & Rules](#14-important-notes--rules)

---

## 1. Overview

GRPO (Goods Receipt Purchase Order) is posted to SAP Business One via the **Service Layer API**:

```
POST /b1s/v2/PurchaseDeliveryNotes
```

**Flow:**
```
Gate Entry Completed -> QC Done -> User reviews items -> POST /api/grpo/post/ -> SAP
```

**What changed:**
- PO linking now works (BaseEntry/BaseLine/BaseType = 22)
- New line-level fields: UnitPrice, TaxCode, AccountCode, U_Variety
- Extra charges via DocumentAdditionalExpenses
- Vendor reference (NumAtCard)
- Structured comments (App + User + PO + Gate Entry + user remarks)
- Address fields removed (SAP auto-inherits from PO when using BaseEntry)

---

## 2. API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/grpo/pending/` | List completed entries pending GRPO posting |
| GET | `/api/grpo/preview/<vehicle_entry_id>/` | Preview GRPO data for a gate entry |
| **POST** | **`/api/grpo/post/`** | **Post GRPO to SAP** |
| GET | `/api/grpo/history/` | GRPO posting history |
| GET | `/api/grpo/<posting_id>/` | GRPO posting detail |

---

## 3. POST /api/grpo/post/ - Full Payload Reference

### 3.1 Minimal Payload (Required Fields Only)

```json
{
    "vehicle_entry_id": 123,
    "po_receipt_id": 456,
    "items": [
        {
            "po_item_receipt_id": 789,
            "accepted_qty": 950.000
        }
    ],
    "branch_id": 1
}
```

### 3.2 Full Payload (All Fields)

```json
{
    "vehicle_entry_id": 123,
    "po_receipt_id": 456,
    "items": [
        {
            "po_item_receipt_id": 789,
            "accepted_qty": 950.000,
            "unit_price": 50.00,
            "tax_code": "GST18",
            "gl_account": "500100",
            "variety": "Grade-A"
        },
        {
            "po_item_receipt_id": 790,
            "accepted_qty": 500.000,
            "unit_price": 75.00,
            "tax_code": "IGST18",
            "gl_account": "500200",
            "variety": "Grade-B"
        }
    ],
    "branch_id": 1,
    "warehouse_code": "WH01",
    "vendor_ref": "INV-2024-001",
    "comments": "Goods received and QC passed",
    "extra_charges": [
        {
            "expense_code": 1,
            "amount": 5000.00,
            "remarks": "Freight charges",
            "tax_code": "GST18"
        },
        {
            "expense_code": 2,
            "amount": 1000.00,
            "remarks": "Loading charges"
        }
    ]
}
```

### 3.3 Field-by-Field Reference

#### Header Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vehicle_entry_id` | integer | YES | ID of the vehicle entry (gate entry) |
| `po_receipt_id` | integer | YES | ID of the PO receipt to post |
| `items` | array | YES | List of items with accepted quantities (min 1) |
| `branch_id` | integer | YES | SAP Branch/Business Place ID (BPLId) |
| `warehouse_code` | string | No | Warehouse code for all line items |
| `vendor_ref` | string | No | Vendor invoice/reference number -> SAP `NumAtCard` |
| `comments` | string | No | User remarks - appended to structured comment |
| `extra_charges` | array | No | Additional expenses (freight, handling, etc.) |

#### Item Fields (inside `items` array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `po_item_receipt_id` | integer | YES | ID of the POItemReceipt record |
| `accepted_qty` | decimal | YES | Accepted quantity to post (min 0, max = received_qty) |
| `unit_price` | decimal | No | Unit price per item -> SAP `UnitPrice` |
| `tax_code` | string | No | Tax code (e.g. "GST18", "IGST18") -> SAP `TaxCode` |
| `gl_account` | string | No | G/L Account code -> SAP `AccountCode` |
| `variety` | string | No | Item variety -> SAP UDF `U_Variety` |

#### Extra Charges Fields (inside `extra_charges` array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `expense_code` | integer | YES | SAP Expense Code (from Additional Expenses setup) |
| `amount` | decimal | YES | Total amount for this charge |
| `remarks` | string | No | Description (e.g. "Freight", "Loading") |
| `tax_code` | string | No | Tax code for this charge |

### 3.4 Success Response (201 Created)

```json
{
    "success": true,
    "grpo_posting_id": 45,
    "sap_doc_entry": 12345,
    "sap_doc_num": 1001,
    "sap_doc_total": 47500.00,
    "message": "GRPO posted successfully. SAP Doc Num: 1001"
}
```

### 3.5 Error Responses

**400 Bad Request - Validation Error:**
```json
{
    "detail": "Invalid request data",
    "errors": {
        "items": ["At least one item with accepted quantity is required"],
        "branch_id": ["This field is required."]
    }
}
```

**400 Bad Request - Business Logic Error:**
```json
{
    "detail": "GRPO already posted for PO PO-001. SAP Doc Num: 1001"
}
```

**400 Bad Request - SAP Validation Error:**
```json
{
    "detail": "SAP validation error: Quantity exceeds open PO quantity"
}
```

**502 Bad Gateway - SAP Error:**
```json
{
    "detail": "SAP error: Failed to create GRPO: ..."
}
```

**503 Service Unavailable - SAP Down:**
```json
{
    "detail": "SAP system is currently unavailable. Please try again later."
}
```

---

## 4. SAP Payload (What Gets Sent to SAP)

When you call `POST /api/grpo/post/`, the service builds this SAP payload and sends it to `POST /b1s/v2/PurchaseDeliveryNotes`:

### 4.1 Complete SAP Payload Example

```json
{
    "CardCode": "V00001",
    "BPL_IDAssignedToInvoice": 1,
    "NumAtCard": "INV-2024-001",
    "Comments": "App: FactoryApp v2 | User: John Doe (john@example.com) | PO: 4500001234 | Gate Entry: VE-2024-001 | Goods received and QC passed",
    "DocumentLines": [
        {
            "ItemCode": "RM-001",
            "Quantity": "950.000",
            "BaseEntry": 12345,
            "BaseLine": 0,
            "BaseType": 22,
            "WarehouseCode": "WH01",
            "UnitPrice": 50.0,
            "TaxCode": "GST18",
            "AccountCode": "500100",
            "U_Variety": "Grade-A"
        },
        {
            "ItemCode": "RM-002",
            "Quantity": "500.000",
            "BaseEntry": 12345,
            "BaseLine": 1,
            "BaseType": 22,
            "WarehouseCode": "WH01",
            "UnitPrice": 75.0,
            "AccountCode": "500200"
        }
    ],
    "DocumentAdditionalExpenses": [
        {
            "ExpenseCode": 1,
            "LineTotal": 5000.0,
            "Remarks": "Freight charges",
            "TaxCode": "GST18"
        }
    ]
}
```

### 4.2 Mapping: Our API -> SAP Payload

| Our API Field | SAP Field | Where |
|---------------|-----------|-------|
| (from POReceipt.supplier_code) | `CardCode` | Header |
| `branch_id` | `BPL_IDAssignedToInvoice` | Header |
| `vendor_ref` | `NumAtCard` | Header |
| (auto-built) | `Comments` | Header |
| `items[].accepted_qty` | `DocumentLines[].Quantity` | Line |
| (from POItemReceipt.po_item_code) | `DocumentLines[].ItemCode` | Line |
| (from POReceipt.sap_doc_entry) | `DocumentLines[].BaseEntry` | Line |
| (from POItemReceipt.sap_line_num) | `DocumentLines[].BaseLine` | Line |
| (constant = 22) | `DocumentLines[].BaseType` | Line |
| `warehouse_code` | `DocumentLines[].WarehouseCode` | Line |
| `items[].unit_price` | `DocumentLines[].UnitPrice` | Line |
| `items[].tax_code` | `DocumentLines[].TaxCode` | Line |
| `items[].gl_account` | `DocumentLines[].AccountCode` | Line |
| `items[].variety` | `DocumentLines[].U_Variety` | Line |
| `extra_charges[].expense_code` | `DocumentAdditionalExpenses[].ExpenseCode` | Expense |
| `extra_charges[].amount` | `DocumentAdditionalExpenses[].LineTotal` | Expense |
| `extra_charges[].remarks` | `DocumentAdditionalExpenses[].Remarks` | Expense |
| `extra_charges[].tax_code` | `DocumentAdditionalExpenses[].TaxCode` | Expense |

---

## 5. PO Linking (BaseEntry / BaseLine / BaseType)

### How It Works

PO linking connects the GRPO to the original Purchase Order in SAP. This is **critical** because:
- SAP reduces the PO open quantity automatically
- SAP closes the PO when all lines are fully received
- Full traceability: PO -> GRPO -> AP Invoice chain
- Prevents duplicate receipts

### Where the Values Come From

```
POReceipt.sap_doc_entry  -->  BaseEntry  (PO DocEntry from HANA OPOR table)
POItemReceipt.sap_line_num  -->  BaseLine  (PO line number from HANA POR1 table)
22 (constant)  -->  BaseType  (22 = Purchase Order in SAP)
```

These values are **automatically stored** when receiving a PO via `POST /api/raw-material/<gate_entry_id>/receive-po/`:
- The `ReceivePOAPI` fetches open POs from SAP HANA
- Stores `po.doc_entry` in `POReceipt.sap_doc_entry`
- Stores `item.line_num` in `POItemReceipt.sap_line_num`

### Automatic Behavior

- If `sap_doc_entry` and `sap_line_num` are both present, PO linking fields are **automatically included** in the SAP payload
- If either is missing (null), the GRPO is posted as **standalone** (no PO link)
- No manual input needed from the frontend for PO linking

### SAP Rules When PO Linking is Active

| Rule | Description |
|------|-------------|
| Quantity <= Open Qty | `Quantity` cannot exceed the PO line's remaining open quantity |
| ItemCode must match | `ItemCode` must match the PO line item |
| Auto-close PO | If all PO lines are fully received, SAP closes the PO automatically |
| Auto-fill fields | SAP may auto-fill UnitPrice, TaxCode, AccountCode from the PO |
| Address inherited | SAP auto-inherits ShipToCode/PayToCode from the PO (no need to send) |

---

## 6. Line-Level Fields (Per Item)

All line-level fields are **optional**. When PO linking is active, SAP can auto-fill many of these from the PO.

### UnitPrice

```json
{ "unit_price": 50.00 }  -->  { "UnitPrice": 50.0 }
```
- Per-unit price for the item
- If omitted and PO linking is active, SAP uses the PO price
- Type: decimal (up to 18 digits, 6 decimal places)

### TaxCode

```json
{ "tax_code": "GST18" }  -->  { "TaxCode": "GST18" }
```
- SAP tax code for this line
- Common values: `GST18`, `IGST18`, `GST5`, `EXEMPT`
- If omitted and PO linking is active, SAP uses the PO tax code
- Must be a valid tax code configured in SAP

### AccountCode (G/L Account)

```json
{ "gl_account": "500100" }  -->  { "AccountCode": "500100" }
```
- General Ledger account to charge
- If omitted and PO linking is active, SAP uses the PO account
- **Mandatory for consumable items** (non-PO linked GRPOs)
- Must be a valid G/L account in SAP

### U_Variety (UDF)

```json
{ "variety": "Grade-A" }  -->  { "U_Variety": "Grade-A" }
```
- User Defined Field in SAP for item variety/grade
- This is a **custom field** - must be configured in SAP B1 (UDF Manager)
- If not configured in SAP, the post will fail with a validation error

---

## 7. Extra Charges (DocumentAdditionalExpenses)

Extra charges (freight, handling, insurance, loading, etc.) are posted as SAP `DocumentAdditionalExpenses`.

### How to Send

```json
{
    "extra_charges": [
        {
            "expense_code": 1,
            "amount": 5000.00,
            "remarks": "Freight charges",
            "tax_code": "GST18"
        },
        {
            "expense_code": 2,
            "amount": 1000.00,
            "remarks": "Loading charges"
        }
    ]
}
```

### Expense Code

The `expense_code` must be a valid code from SAP's **Additional Expenses** setup:
- In SAP B1: Administration > Setup > General > Additional Expenses
- Common codes vary per SAP installation
- Ask the SAP admin for valid expense codes

### SAP Payload Generated

```json
{
    "DocumentAdditionalExpenses": [
        {
            "ExpenseCode": 1,
            "LineTotal": 5000.0,
            "Remarks": "Freight charges",
            "TaxCode": "GST18"
        }
    ]
}
```

---

## 8. Structured Comments

Comments are **automatically built** with a structured format. The user's `comments` field value is appended at the end.

### Format

```
App: FactoryApp v2 | User: <full_name> (<email>) | PO: <po_number> | Gate Entry: <entry_no> | <user_comments>
```

### Example

If you send:
```json
{ "comments": "Goods received and QC passed" }
```

SAP receives:
```
App: FactoryApp v2 | User: Naresh Kumar (naresh@example.com) | PO: 4500001234 | Gate Entry: VE-2024-001 | Goods received and QC passed
```

If `comments` is empty or not provided, the structured part is still sent (without the trailing part):
```
App: FactoryApp v2 | User: Naresh Kumar (naresh@example.com) | PO: 4500001234 | Gate Entry: VE-2024-001
```

---

## 9. Vendor Reference (NumAtCard)

The `vendor_ref` field maps to SAP's `NumAtCard` field which stores the vendor's own reference number (their invoice number, challan number, etc.).

```json
{ "vendor_ref": "INV-2024-001" }  -->  { "NumAtCard": "INV-2024-001" }
```

- Optional field
- Visible in SAP B1 as "Vendor Ref. No." on the GRPO document
- Useful for cross-referencing with the vendor's own numbering system

---

## 10. SAP Field Mapping (Complete)

### Header Level

| SAP Field | Type | Required | Source | Currently Sent |
|-----------|------|----------|--------|---------------|
| `CardCode` | string | YES | POReceipt.supplier_code | YES |
| `BPL_IDAssignedToInvoice` | int | YES | API: branch_id | YES |
| `Comments` | string | No | Auto-built structured comment | YES |
| `NumAtCard` | string | No | API: vendor_ref | YES (if provided) |

### Line Level (DocumentLines)

| SAP Field | Type | Required | Source | Currently Sent |
|-----------|------|----------|--------|---------------|
| `ItemCode` | string | YES | POItemReceipt.po_item_code | YES |
| `Quantity` | string | YES | API: accepted_qty | YES |
| `BaseEntry` | int | YES (for PO link) | POReceipt.sap_doc_entry | YES (auto) |
| `BaseLine` | int | YES (for PO link) | POItemReceipt.sap_line_num | YES (auto) |
| `BaseType` | int | YES (for PO link) | Constant: 22 | YES (auto) |
| `WarehouseCode` | string | No | API: warehouse_code | YES (if provided) |
| `UnitPrice` | decimal | No | API: unit_price | YES (if provided) |
| `TaxCode` | string | No | API: tax_code | YES (if provided) |
| `AccountCode` | string | No | API: gl_account | YES (if provided) |
| `U_Variety` | string | No | API: variety | YES (if provided) |

### Additional Expenses (DocumentAdditionalExpenses)

| SAP Field | Type | Required | Source | Currently Sent |
|-----------|------|----------|--------|---------------|
| `ExpenseCode` | int | YES | API: expense_code | YES (if provided) |
| `LineTotal` | decimal | YES | API: amount | YES (if provided) |
| `Remarks` | string | No | API: remarks | YES (if provided) |
| `TaxCode` | string | No | API: tax_code | YES (if provided) |

---

## 11. Error Handling

### Validation Errors (Before SAP Call)

| Error | Cause | HTTP Status |
|-------|-------|-------------|
| "At least one item with accepted quantity is required" | Empty items array | 400 |
| "This field is required." (branch_id, etc.) | Missing required fields | 400 |
| "Vehicle entry X not found" | Invalid vehicle_entry_id | 400 |
| "PO receipt X not found for this vehicle entry" | Invalid po_receipt_id | 400 |
| "Invalid PO item receipt IDs: {ids}" | Item IDs don't belong to the PO | 400 |
| "Accepted qty (X) cannot exceed received qty (Y)" | Qty validation failed | 400 |
| "GRPO already posted for PO X. SAP Doc Num: Y" | Duplicate posting attempt | 400 |
| "Gate entry is not completed. Current status: X" | Entry not in valid state | 400 |
| "No accepted quantities to post for this PO" | All items have 0 accepted qty | 400 |

### SAP Errors (During SAP Call)

| Error | Cause | HTTP Status |
|-------|-------|-------------|
| "SAP validation error: ..." | SAP rejected the payload (400 from SAP) | 400 |
| "SAP system is currently unavailable" | Cannot connect to SAP | 503 |
| "SAP error: ..." | Other SAP errors | 502 |

### What Happens on Failure

When a GRPO post fails:
1. The `GRPOPosting` record is set to status `FAILED`
2. The `error_message` field stores the error details
3. You can retry by calling `POST /api/grpo/post/` again with the same data
4. The system will reuse the existing `GRPOPosting` record (get_or_create)

---

## 12. End-to-End Flow

```
Step 1: Gate Entry Created
    -> Vehicle arrives, entry recorded

Step 2: PO Received (POST /api/raw-material/<id>/receive-po/)
    -> POReceipt created with sap_doc_entry (from SAP HANA)
    -> POItemReceipt created with sap_line_num (from SAP HANA)
    -> SAP PO data (DocEntry, LineNum) are stored automatically

Step 3: QC Done
    -> Arrival slips submitted, inspections completed
    -> Gate entry status -> COMPLETED or QC_COMPLETED

Step 4: Preview GRPO (GET /api/grpo/preview/<vehicle_entry_id>/)
    -> Returns PO details, items, QC status, sap_doc_entry
    -> Frontend shows preview for user review

Step 5: Post GRPO (POST /api/grpo/post/)
    -> User submits accepted quantities and optional fields
    -> Service validates all data
    -> Builds SAP payload with PO linking
    -> Posts to SAP Service Layer
    -> Stores SAP response (DocEntry, DocNum, DocTotal)
    -> Creates GRPOLinePosting records

Step 6: Verify (GET /api/grpo/history/ or /api/grpo/<id>/)
    -> Check posting status, SAP document numbers
```

---

## 13. Key Files

| File | Purpose |
|------|---------|
| `grpo/services.py` | Core business logic - `GRPOService.post_grpo()` |
| `grpo/models.py` | `GRPOPosting` and `GRPOLinePosting` models |
| `grpo/views.py` | REST API endpoints |
| `grpo/serializers.py` | Request/response validation |
| `grpo/urls.py` | URL routing |
| `grpo/permissions.py` | Permission classes |
| `grpo/tests.py` | Unit tests (22 tests) |
| `sap_client/service_layer/grpo_writer.py` | SAP Service Layer API call |
| `sap_client/client.py` | SAP client entry point |
| `sap_client/dtos.py` | Data Transfer Objects |
| `sap_client/hana/po_reader.py` | Reads PO data (DocEntry, LineNum) from HANA |
| `raw_material_gatein/models/po_receipt.py` | POReceipt model (has `sap_doc_entry`) |
| `raw_material_gatein/models/po_item_receipt.py` | POItemReceipt model (has `sap_line_num`) |
| `raw_material_gatein/views.py` | ReceivePOAPI (stores SAP fields during PO receive) |

---

## 14. Important Notes & Rules

### PO Linking is Automatic
- `sap_doc_entry` is stored in POReceipt when PO is received
- `sap_line_num` is stored in POItemReceipt when PO is received
- GRPO service automatically adds BaseEntry/BaseLine/BaseType if these values exist
- **Frontend does not need to send any PO linking fields**

### Address is NOT Needed
- When PO linking (BaseEntry) is active, SAP **auto-inherits** the address from the PO
- No need to send `ShipToCode` or `PayToCode`
- This is standard SAP B1 behavior for PO-based documents

### Optional Fields Are Truly Optional
- When PO linking is active, SAP auto-fills UnitPrice, TaxCode, AccountCode from the PO
- You only need to send these fields if you want to **override** the PO values
- For a basic GRPO post, only `vehicle_entry_id`, `po_receipt_id`, `items` (with `po_item_receipt_id` + `accepted_qty`), and `branch_id` are required

### U_Variety is a Custom UDF
- This is a User Defined Field - must exist in SAP B1 (UDF Manager > Marketing Documents > Rows)
- If not configured, SAP will reject the payload with a validation error
- Only send this field if the UDF is set up in your SAP instance

### Quantity Validation
- `accepted_qty` cannot exceed the item's `received_qty`
- When PO linking is active, SAP also validates that `Quantity` does not exceed PO open quantity
- If SAP rejects the quantity, you'll get a `SAP validation error` response

### Duplicate Posting Prevention
- The system checks for existing `POSTED` status GRPOs for the same vehicle_entry + po_receipt
- Once posted, the same PO receipt cannot be posted again
- `FAILED` status records can be retried

### Migration Required
- Run `python manage.py migrate` to apply the new `sap_doc_entry` and `sap_line_num` fields
- Migration file: `raw_material_gatein/migrations/0009_add_sap_po_linking_fields.py`
- Existing POReceipt/POItemReceipt records will have `sap_doc_entry`/`sap_line_num` as NULL
- For existing records, PO linking will not be active (standalone GRPO)
