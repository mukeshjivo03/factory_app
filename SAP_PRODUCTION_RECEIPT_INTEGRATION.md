# SAP Production Receipt Integration - Documentation

## Objective

When a production run is **completed** in the Production Execution module, the produced quantity should be posted back to SAP B1 as a **Production Receipt** (Goods Receipt from Production). This updates SAP inventory and closes/partially closes the production order.

---

## What Data We Have at Completion

When `complete_run()` is called, the following data is available from the `ProductionRun` model:

| Field | Description | Example |
|-------|-------------|---------|
| `sap_doc_entry` | SAP Production Order DocEntry (from OWOR table) | `1234` |
| `total_production` | Total units/cases produced (entered by operator) | `500.0` |
| `rejected_qty` | Rejected quantity from QC failures | `10.0` |
| `reworked_qty` | Reworked quantity from QC | `5.0` |
| `product` | Product name (auto-filled from SAP) | `"Finished Good A"` |
| `date` | Production date | `2026-03-28` |

**Note:** `item_code` and `warehouse` are NOT stored on `ProductionRun` model currently. They are fetched from SAP via `sap_doc_entry` using the `ProductionOrderReader`.

---

## Where to Insert in SAP B1

### SAP API Endpoint

**Service Layer URL:** `POST /b1s/v2/InventoryGenEntries`

This creates a **Goods Receipt** document in SAP B1 linked to the production order.

### SAP Tables Affected

| Table | Description |
|-------|-------------|
| `OIGN` | Goods Receipt Header (InventoryGenEntries) |
| `IGN1` | Goods Receipt Lines (document lines) |
| `OWOR` | Production Order — `CmpltQty` gets updated |
| `OITW` | Item Warehouse — stock quantity increases |

---

## SAP Payload Structure

The JSON payload sent to SAP Service Layer:

```json
{
    "DocDate": "2026-03-28",
    "Comments": "Production Receipt from Production Run #1234",
    "DocumentLines": [
        {
            "ItemCode": "FG-001",
            "Quantity": 500.0,
            "WarehouseCode": "WH-01",
            "BaseType": 202,
            "BaseEntry": 1234,
            "BaseLine": 0
        }
    ]
}
```

### Field Explanation

| Payload Field | Source | Description |
|---------------|--------|-------------|
| `DocDate` | `ProductionRun.date` | Posting date of the receipt |
| `Comments` | Auto-generated | Reference back to production run |
| `ItemCode` | Fetched from SAP OWOR using `sap_doc_entry` | The finished good item code |
| `Quantity` | `ProductionRun.total_production` | How many units were produced |
| `WarehouseCode` | Fetched from SAP OWOR using `sap_doc_entry` | Target warehouse for finished goods |
| `BaseType` | Always `202` | SAP object code for Production Order |
| `BaseEntry` | `ProductionRun.sap_doc_entry` | Links receipt to the production order |
| `BaseLine` | Always `0` | Line number in production order (first line) |

---

## Step-by-Step Flow

### Step 1: Operator Completes Production Run
- Operator calls `POST /api/production-execution/runs/<run_id>/complete/`
- Sends `{ "total_production": 500.0 }`

### Step 2: Fetch Item Code & Warehouse from SAP
Before posting to SAP, we need the `ItemCode` and `Warehouse` from the production order:
- Use `ProductionOrderReader.get_production_order_detail(sap_doc_entry)`
- This returns:
  - `header.ItemCode` — e.g., `"FG-001"`
  - `header.Warehouse` — e.g., `"WH-01"`

### Step 3: Authenticate with SAP Service Layer
- `POST /b1s/v2/Login` with CompanyDB, UserName, Password
- This creates an authenticated session

### Step 4: Post Goods Receipt to SAP
- `POST /b1s/v2/InventoryGenEntries` with the payload above
- SAP returns the created document's `DocEntry`

### Step 5: Store SAP Response
- Save the SAP Goods Receipt `DocEntry` back on the `ProductionRun` for traceability
- **Requires new field:** `sap_receipt_doc_entry` on `ProductionRun` model

### Step 6: Handle Errors
- If SAP posting fails, the production run should still be marked as completed locally
- Log the SAP error and flag the run for manual retry
- **Requires new field:** `sap_sync_status` (e.g., `PENDING`, `SUCCESS`, `FAILED`)

---

## Existing Code Reference

### Already Built (sap_writer.py)
The file `production_execution/services/sap_writer.py` already has a `GoodsReceiptWriter` class with:
- SAP Service Layer authentication
- `post_goods_receipt(doc_entry, item_code, warehouse, qty, posting_date)` method
- Posts to `InventoryGenEntries` endpoint
- Error handling

**This writer is currently NOT called anywhere.** It needs to be integrated into the `complete_run()` flow.

### Where to Integrate (production_service.py)
The `complete_run()` method in `production_service.py` is where the SAP posting should happen:
- After setting `run.status = COMPLETED`
- After `run.save()`
- Call `GoodsReceiptWriter.post_goods_receipt()`

---

## New Fields Needed on ProductionRun Model

| Field | Type | Purpose |
|-------|------|---------|
| `sap_receipt_doc_entry` | IntegerField (nullable) | Stores SAP Goods Receipt DocEntry after successful post |
| `sap_sync_status` | CharField (choices) | Tracks SAP sync state: `PENDING`, `SUCCESS`, `FAILED`, `NOT_APPLICABLE` |
| `sap_sync_error` | TextField (nullable) | Stores error message if SAP post fails |

---

## Quantity Considerations

| Scenario | What to Post to SAP |
|----------|-------------------|
| Normal completion | `total_production` (full produced qty) |
| With rejections | `total_production - rejected_qty` (only good units) |
| Partial production | Post whatever was produced; SAP production order remains open |
| Multiple runs for same SAP order | Each run posts its own receipt; SAP accumulates `CmpltQty` |

**Decision needed:** Should we post `total_production` or `total_production - rejected_qty`? This depends on business rules — rejected items may or may not enter inventory.

---

## Authentication Details

SAP Service Layer credentials are configured in the `SAPClient` via company-specific settings:

```
base_url:    Service Layer base URL (e.g., https://sap-server:50000)
company_db:  SAP Company Database name
username:    SAP Service Layer username
password:    SAP Service Layer password
```

These are accessed via `self.client.context.service_layer` in the existing `GoodsReceiptWriter`.

---

## Summary

| What | Detail |
|------|--------|
| **SAP Endpoint** | `POST /b1s/v2/InventoryGenEntries` |
| **Trigger** | When `complete_run()` is called |
| **Data Source** | `ProductionRun` model + SAP OWOR lookup |
| **Existing Code** | `sap_writer.py` — `GoodsReceiptWriter` (built but unused) |
| **Integration Point** | `production_service.py` — `complete_run()` method |
| **New Fields** | `sap_receipt_doc_entry`, `sap_sync_status`, `sap_sync_error` |
