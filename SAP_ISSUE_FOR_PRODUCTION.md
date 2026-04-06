# SAP Issue for Production — Complete Integration Guide

## Overview

**Issue for Production** (also called "Goods Issue for Production" or "Material Issue") is the process of issuing raw materials/components from inventory to a production order. In SAP Business One, this reduces warehouse stock and links consumed materials to the production order.

### SAP Terminology

| Term | SAP Object | Table | Service Layer Endpoint |
|------|-----------|-------|----------------------|
| Issue for Production | Inventory Gen Exit | `OIGE` (header) / `IGE1` (lines) | `POST /b1s/v2/InventoryGenExits` |
| Production Order | Production Order | `OWOR` (header) / `WOR1` (components) | `GET /b1s/v2/ProductionOrders` |

### What Happens in SAP When You Issue Materials

1. Raw material stock **decreases** in the source warehouse
2. `WOR1.IssuedQty` **increases** for the corresponding component line
3. An `OIGE` document is created with audit trail
4. GL postings are made (Raw Material A/C → WIP A/C)

---

## Data Flow: Issue for Production

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  User selects Production Order → sees BOM components        │
│  → enters qty to issue per component → submits              │
└───────────────────────┬─────────────────────────────────────┘
                        │ POST /api/production-execution/runs/{id}/issue-materials/
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                Django REST API                               │
│  IssueMaterialsAPI.post()                                   │
│  └─> ProductionExecutionService.issue_materials_to_sap()    │
└───────────┬──────────────────────────────────┬──────────────┘
            │                                  │
            ▼                                  ▼
   ┌──────────────────┐           ┌────────────────────────┐
   │ HANA SQL (Read)  │           │ Service Layer (Write)  │
   │                  │           │                        │
   │ 1. Fetch OWOR    │           │ POST /b1s/v2/          │
   │    header        │           │ InventoryGenExits      │
   │ 2. Fetch WOR1    │           │                        │
   │    components    │           │ Creates OIGE document  │
   │    (BOM lines)   │           │ Reduces warehouse qty  │
   └──────────────────┘           └────────────────────────┘
```

---

## SAP Tables Involved

### OIGE — Goods Issue Header

| Column | Type | Description |
|--------|------|-------------|
| `DocEntry` | INT | Unique document ID (auto-generated) |
| `DocNum` | INT | Document number |
| `DocDate` | DATE | Posting date |
| `TaxDate` | DATE | Tax date (usually = DocDate) |
| `Comments` | NVARCHAR | Free-text remarks |
| `JrnlMemo` | NVARCHAR | Journal memo |
| `Series` | INT | Document series |

### IGE1 — Goods Issue Lines

| Column | Type | Description |
|--------|------|-------------|
| `DocEntry` | INT | FK to OIGE |
| `LineNum` | INT | Line number (0-based) |
| `ItemCode` | NVARCHAR | Material/item code |
| `Quantity` | DECIMAL | Quantity to issue |
| `WhsCode` | NVARCHAR | Source warehouse code |
| `AccountCode` | NVARCHAR | GL account (auto from item group) |
| `BaseType` | INT | **202** (Production Order) |
| `BaseEntry` | INT | Production Order DocEntry |
| `BaseLine` | INT | WOR1 line number (0-based) |
| `UomEntry` | INT | UOM entry ID |
| `UoMCode` | NVARCHAR | UOM code |

### WOR1 — Production Order Components (Reference)

| Column | Type | Description |
|--------|------|-------------|
| `DocEntry` | INT | FK to OWOR |
| `LineNum` | INT | Line number (0-based) |
| `ItemCode` | NVARCHAR | Component item code |
| `ItemName` | NVARCHAR | Component name |
| `PlannedQty` | DECIMAL | BOM planned quantity |
| `IssuedQty` | DECIMAL | Already issued quantity |
| `wareHouse` | NVARCHAR | Component warehouse |
| `UomCode` | NVARCHAR | Unit of measure |

---

## API Endpoint Design

### 1. Get Components Available for Issue

**Endpoint:** `GET /api/production-execution/sap/orders/{doc_entry}/components-for-issue/`

**Purpose:** Fetch production order components with issued vs planned qty to show what can still be issued.

**HANA SQL Query:**
```sql
SELECT
    W."DocEntry",
    W."DocNum",
    W."ItemCode"   AS "ProductCode",
    W."ProdName"   AS "ProductName",
    W."PlannedQty",
    W."CmpltQty",
    W."Warehouse",
    W."Status",
    C."LineNum",
    C."ItemCode"   AS "ComponentCode",
    C."ItemName"   AS "ComponentName",
    C."PlannedQty" AS "ComponentPlannedQty",
    C."IssuedQty"  AS "ComponentIssuedQty",
    (C."PlannedQty" - C."IssuedQty") AS "RemainingToIssue",
    C."wareHouse"  AS "ComponentWarehouse",
    C."UomCode"    AS "ComponentUOM"
FROM "{schema}"."OWOR" W
INNER JOIN "{schema}"."WOR1" C ON W."DocEntry" = C."DocEntry"
WHERE W."DocEntry" = {doc_entry}
  AND W."Status" = 'R'
ORDER BY C."LineNum" ASC
```

**Response:**
```json
{
    "production_order": {
        "DocEntry": 1234,
        "DocNum": 5001,
        "ProductCode": "FG-OIL-1L",
        "ProductName": "Jivo Canola Oil 1L",
        "PlannedQty": 1000.0,
        "CmpltQty": 0.0,
        "Warehouse": "FG-WH",
        "Status": "R"
    },
    "components": [
        {
            "LineNum": 0,
            "ComponentCode": "RM-CANOLA-OIL",
            "ComponentName": "Canola Oil Crude",
            "ComponentPlannedQty": 1050.0,
            "ComponentIssuedQty": 0.0,
            "RemainingToIssue": 1050.0,
            "ComponentWarehouse": "RM-WH",
            "ComponentUOM": "LTR"
        },
        {
            "LineNum": 1,
            "ComponentCode": "PM-BOTTLE-1L",
            "ComponentName": "PET Bottle 1 Litre",
            "ComponentPlannedQty": 1000.0,
            "ComponentIssuedQty": 500.0,
            "RemainingToIssue": 500.0,
            "ComponentWarehouse": "PM-WH",
            "ComponentUOM": "PCS"
        },
        {
            "LineNum": 2,
            "ComponentCode": "PM-CAP-38MM",
            "ComponentName": "Cap 38mm",
            "ComponentPlannedQty": 1000.0,
            "ComponentIssuedQty": 0.0,
            "RemainingToIssue": 1000.0,
            "ComponentWarehouse": "PM-WH",
            "ComponentUOM": "PCS"
        },
        {
            "LineNum": 3,
            "ComponentCode": "PM-LABEL-1L",
            "ComponentName": "Label Jivo Canola 1L",
            "ComponentPlannedQty": 1010.0,
            "ComponentIssuedQty": 0.0,
            "RemainingToIssue": 1010.0,
            "ComponentWarehouse": "PM-WH",
            "ComponentUOM": "PCS"
        }
    ]
}
```

---

### 2. Issue Materials for Production (Post to SAP)

**Endpoint:** `POST /api/production-execution/runs/{run_id}/issue-materials/`

**Purpose:** Issue selected raw materials/components to the production order in SAP.

**Request Payload:**
```json
{
    "posting_date": "2026-04-06",
    "remarks": "Issue for Production Run #3 - Morning Shift",
    "lines": [
        {
            "component_code": "RM-CANOLA-OIL",
            "quantity": 500.0,
            "warehouse": "RM-WH",
            "base_line": 0
        },
        {
            "component_code": "PM-BOTTLE-1L",
            "quantity": 500.0,
            "warehouse": "PM-WH",
            "base_line": 1
        },
        {
            "component_code": "PM-CAP-38MM",
            "quantity": 500.0,
            "warehouse": "PM-WH",
            "base_line": 2
        },
        {
            "component_code": "PM-LABEL-1L",
            "quantity": 510.0,
            "warehouse": "PM-WH",
            "base_line": 3
        }
    ]
}
```

#### Payload Field Details

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `posting_date` | string (YYYY-MM-DD) | Yes | Date of material issue |
| `remarks` | string | No | Free-text comments for the SAP document |
| `lines` | array | Yes | Array of material lines to issue |
| `lines[].component_code` | string | Yes | SAP ItemCode of the component (from WOR1) |
| `lines[].quantity` | number | Yes | Quantity to issue (must be > 0) |
| `lines[].warehouse` | string | Yes | Source warehouse code (from WOR1.wareHouse) |
| `lines[].base_line` | integer | Yes | WOR1 LineNum (0-based) — links issue to BOM line |

---

## SAP Service Layer Payload

### Authentication

```
POST https://103.89.45.192:50000/b1s/v2/Login

{
    "CompanyDB": "TEST_OIL_15122025",
    "UserName": "B1i",
    "Password": "1234"
}
```

### Issue for Production — InventoryGenExits

```
POST https://103.89.45.192:50000/b1s/v2/InventoryGenExits

Headers:
  Content-Type: application/json
  Cookie: <session cookie from Login>

Body:
{
    "DocDate": "2026-04-06",
    "Comments": "Issue for Production — PO DocEntry 1234, Run #3",
    "DocumentLines": [
        {
            "ItemCode": "RM-CANOLA-OIL",
            "Quantity": 500.0,
            "WarehouseCode": "RM-WH",
            "BaseType": 202,
            "BaseEntry": 1234,
            "BaseLine": 0
        },
        {
            "ItemCode": "PM-BOTTLE-1L",
            "Quantity": 500.0,
            "WarehouseCode": "PM-WH",
            "BaseType": 202,
            "BaseEntry": 1234,
            "BaseLine": 1
        },
        {
            "ItemCode": "PM-CAP-38MM",
            "Quantity": 500.0,
            "WarehouseCode": "PM-WH",
            "BaseType": 202,
            "BaseEntry": 1234,
            "BaseLine": 2
        },
        {
            "ItemCode": "PM-LABEL-1L",
            "Quantity": 510.0,
            "WarehouseCode": "PM-WH",
            "BaseType": 202,
            "BaseEntry": 1234,
            "BaseLine": 3
        }
    ]
}
```

### Payload Field Mapping

| JSON Field | SAP Field | Table | Description |
|------------|-----------|-------|-------------|
| `DocDate` | `OIGE.DocDate` | OIGE | Posting date |
| `Comments` | `OIGE.Comments` | OIGE | Document remarks |
| `DocumentLines[].ItemCode` | `IGE1.ItemCode` | IGE1 | Component material code |
| `DocumentLines[].Quantity` | `IGE1.Quantity` | IGE1 | Quantity to issue |
| `DocumentLines[].WarehouseCode` | `IGE1.WhsCode` | IGE1 | Source warehouse |
| `DocumentLines[].BaseType` | `IGE1.BaseType` | IGE1 | **202** = Production Order |
| `DocumentLines[].BaseEntry` | `IGE1.BaseEntry` | IGE1 | Production Order DocEntry |
| `DocumentLines[].BaseLine` | `IGE1.BaseLine` | IGE1 | WOR1 LineNum (0-based) |

### Key Rules

- **BaseType must be 202** — this links the goods issue to a production order
- **BaseEntry** = `OWOR.DocEntry` of the production order
- **BaseLine** = `WOR1.LineNum` — the specific BOM component line being issued
- **Quantity** must not exceed `WOR1.PlannedQty - WOR1.IssuedQty` (remaining qty)
- **WarehouseCode** should match `WOR1.wareHouse` (component warehouse)
- Production order **Status must be 'R'** (Released) to accept material issues
- You can do **partial issues** — issue some components now, rest later
- Each issue creates a separate `OIGE` document in SAP

---

## Success Response

```json
{
    "DocEntry": 789,
    "DocNum": 1001,
    "DocumentLines": [
        {
            "LineNum": 0,
            "ItemCode": "RM-CANOLA-OIL",
            "Quantity": 500.0,
            "WarehouseCode": "RM-WH"
        }
    ]
}
```

## Error Response

```json
{
    "error": {
        "code": -10,
        "message": {
            "lang": "en-us",
            "value": "Quantity exceeds the defined quantity for this row [IGE1.BaseLine][line: 1]"
        }
    }
}
```

### Common SAP Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Quantity exceeds defined quantity | Issue qty > remaining planned qty | Reduce quantity or check already-issued amounts |
| Item not found | Invalid ItemCode | Verify component code from WOR1 |
| Warehouse not found | Invalid warehouse code | Verify warehouse from WOR1.wareHouse |
| Document is not released | Production order not in status 'R' | Only issue to Released orders |
| Insufficient inventory | Warehouse stock < issue qty | Check stock via OITW table |

---

## Validation Rules (Before Posting)

### Frontend Validations

1. **At least one line** must be present in the issue
2. **Quantity > 0** for every line
3. **Quantity <= RemainingToIssue** (`PlannedQty - IssuedQty`) for each component
4. **Posting date** must be valid and not in the future
5. **Warehouse** must match the component's assigned warehouse

### Backend Validations

1. Production Run must exist and be linked to a SAP production order (`sap_doc_entry` is not null)
2. Production order must be in **Released** status (`OWOR.Status = 'R'`)
3. Component `ItemCode` must exist in `WOR1` for the given production order
4. `BaseLine` must be a valid `WOR1.LineNum` for the production order
5. Issue quantity must not exceed `WOR1.PlannedQty - WOR1.IssuedQty`
6. Warehouse stock must be sufficient (optional check via `OITW` table)

---

## Stock Check Query (Optional Pre-validation)

Before issuing, you can verify warehouse stock:

```sql
SELECT
    T0."ItemCode",
    T0."ItemName",
    T1."WhsCode",
    T1."OnHand",
    T1."IsCommited",
    T1."OnOrder",
    (T1."OnHand" - T1."IsCommited") AS "AvailableQty"
FROM "{schema}"."OITM" T0
INNER JOIN "{schema}"."OITW" T1 ON T0."ItemCode" = T1."ItemCode"
WHERE T0."ItemCode" = '{item_code}'
  AND T1."WhsCode" = '{warehouse}'
```

---

## Complete API Response Design

### POST /api/production-execution/runs/{run_id}/issue-materials/

**Success Response (201):**
```json
{
    "status": "success",
    "message": "Materials issued successfully to SAP",
    "sap_issue_doc_entry": 789,
    "sap_issue_doc_num": 1001,
    "lines_issued": 4,
    "production_order": 1234
}
```

**Validation Error (400):**
```json
{
    "status": "error",
    "message": "Validation failed",
    "errors": [
        "Line 0: Quantity 2000.0 exceeds remaining qty 1050.0 for RM-CANOLA-OIL",
        "Line 3: Component PM-LABEL-XL not found in production order BOM"
    ]
}
```

**SAP Error (502):**
```json
{
    "status": "error",
    "message": "SAP posting failed",
    "sap_error": "Insufficient inventory for item RM-CANOLA-OIL in warehouse RM-WH"
}
```

---

## Multiple Issues (Partial Issue Flow)

A production order can have **multiple issue documents**. Common scenarios:

| Scenario | Example |
|----------|---------|
| **Shift-wise issue** | Morning shift issues 500 bottles, afternoon shift issues 500 more |
| **Partial BOM issue** | Issue raw oil today, issue packaging materials tomorrow |
| **Over-issue** | If SAP allows, issue more than planned qty (depends on settings) |
| **Different warehouses** | Issue same material from different warehouses in separate docs |

After each issue, `WOR1.IssuedQty` is updated automatically by SAP. The next API call to fetch components will reflect the new `IssuedQty`.

---

## Integration with Existing Production Run

### How This Connects to the Current System

```
Production Run Lifecycle:
                                          
  CREATE RUN ──► IN PROGRESS ──► COMPLETE
       │              │              │
       │              │              │
       ▼              ▼              ▼
  Auto-fetch     Issue Materials   Post Goods Receipt
  BOM from SAP   (THIS FEATURE)   (Already implemented)
  (WOR1/ITT1)    ──────────────   InventoryGenEntries
                  InventoryGenExits
                  Reduces stock
                  Updates WOR1.IssuedQty
```

### Model Changes Needed

Add to `ProductionRun` model:
```python
# SAP Material Issue tracking
sap_issue_doc_entries = models.JSONField(
    default=list, blank=True,
    help_text="List of SAP Goods Issue DocEntries [{doc_entry, doc_num, date, lines_count}]"
)
sap_issue_status = models.CharField(
    max_length=20,
    choices=[
        ('NOT_ISSUED', 'Not Issued'),
        ('PARTIALLY_ISSUED', 'Partially Issued'),
        ('FULLY_ISSUED', 'Fully Issued'),
    ],
    default='NOT_ISSUED',
    help_text="Overall material issue status"
)
```

### Material Usage Tracking Update

When materials are issued to SAP, update `ProductionMaterialUsage.issued_qty`:
```python
# After successful SAP issue, update local tracking
for line in issued_lines:
    ProductionMaterialUsage.objects.filter(
        production_run=run,
        material_code=line['component_code']
    ).update(issued_qty=F('issued_qty') + line['quantity'])
```

---

## Implementation Files

| File | Purpose |
|------|---------|
| `production_execution/services/sap_writer.py` | Add `GoodsIssueWriter` class |
| `production_execution/services/sap_reader.py` | Add `get_components_for_issue()` method |
| `production_execution/services/production_service.py` | Add `issue_materials_to_sap()` method |
| `production_execution/views.py` | Add `IssueMaterialsAPI` view |
| `production_execution/serializers.py` | Add `IssueMaterialSerializer` |
| `production_execution/urls.py` | Add URL route |
| `production_execution/models.py` | Add issue tracking fields |

---

## GoodsIssueWriter Class (Service Layer Writer)

```python
class GoodsIssueWriter:
    """Posts material issues for production to SAP B1 Service Layer."""

    def __init__(self, company_code: str):
        self.company_code = company_code
        from sap_client.client import SAPClient
        self.client = SAPClient(company_code=company_code)

    def post_issue_for_production(
        self,
        doc_entry: int,
        lines: list,
        posting_date,
        remarks: str = '',
    ) -> dict:
        """
        Post a goods issue (InventoryGenExits) for a production order.
        
        Args:
            doc_entry: SAP Production Order DocEntry (OWOR.DocEntry)
            lines: List of dicts with keys:
                   component_code, quantity, warehouse, base_line
            posting_date: Date for the posting
            remarks: Optional comments
            
        Returns:
            dict with DocEntry and DocNum of created OIGE document
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
            raise SAPWriteError(f"SAP login failed: {login_resp.text}")

        # Build payload
        document_lines = []
        for line in lines:
            document_lines.append({
                "ItemCode": line['component_code'],
                "Quantity": float(line['quantity']),
                "WarehouseCode": line['warehouse'],
                "BaseType": 202,
                "BaseEntry": doc_entry,
                "BaseLine": line['base_line'],
            })

        payload = {
            "DocDate": (
                posting_date.isoformat()
                if hasattr(posting_date, 'isoformat')
                else str(posting_date)
            ),
            "Comments": remarks or f"Issue for Production — DocEntry {doc_entry}",
            "DocumentLines": document_lines,
        }

        # Post to SAP
        response = session.post(
            f"{base_url}/b1s/v2/InventoryGenExits",
            json=payload,
            timeout=30,
            verify=False,
        )

        if not response.ok:
            error_msg = self._extract_error(response)
            raise SAPWriteError(f"Failed to post issue to SAP: {error_msg}")

        result = response.json()
        return {
            'DocEntry': result.get('DocEntry'),
            'DocNum': result.get('DocNum'),
        }

    @staticmethod
    def _extract_error(response) -> str:
        try:
            data = response.json()
            return data.get('error', {}).get('message', {}).get('value', response.text)
        except Exception:
            return response.text
```

---

## Summary: Goods Receipt vs Goods Issue

| Aspect | Goods Receipt (Existing) | Goods Issue (New) |
|--------|-------------------------|-------------------|
| **SAP Object** | Inventory Gen Entry (OIGN) | Inventory Gen Exit (OIGE) |
| **Service Layer** | `POST /b1s/v2/InventoryGenEntries` | `POST /b1s/v2/InventoryGenExits` |
| **BaseType** | 202 (Production Order) | 202 (Production Order) |
| **Stock Effect** | Increases finished goods stock | Decreases raw material stock |
| **When** | On production completion | During/before production |
| **Lines** | Single line (finished product) | Multiple lines (BOM components) |
| **Qty Source** | `total_production - rejected_qty` | User-entered per component |
| **Warehouse** | Finished goods warehouse (OWOR) | Component warehouse (WOR1) |
