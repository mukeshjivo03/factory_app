,# SAP Production Module – Data Integration Detail

## Overview

The Production SAP module integrates the Factory App's production execution workflow with SAP Business One via two channels:

- **SAP HANA (Direct SQL)** – For reading production orders, BOMs, and item master data
- **SAP Service Layer (REST API)** – For posting goods receipts back to SAP

---

## 1. Data Inserted / Posted INTO SAP

### 1.1 Production Goods Receipt

When a production run is completed, a **Goods Receipt (Inventory Gen Entry)** is posted to SAP.

| Property | Description |
|----------|-------------|
| **SAP Endpoint** | `POST /b1s/v2/InventoryGenEntries` |
| **Trigger** | `CompleteRunAPI.post()` → `ProductionExecutionService.complete_run()` |
| **Writer Class** | `GoodsReceiptWriter` in `production_execution/services/sap_writer.py` |
| **Service Method** | `_post_goods_receipt_to_sap()` in `production_execution/services/production_service.py` |

#### Payload Structure

```json
{
  "DocDate": "2026-03-28",
  "Comments": "Production Execution — DocEntry 1234",
  "DocumentLines": [
    {
      "ItemCode": "FG-001",
      "Quantity": 490.0,
      "WarehouseCode": "WH-01",
      "BaseType": 202,
      "BaseEntry": 1234,
      "BaseLine": 0
    }
  ]
}
```

#### Field-by-Field Detail

| Field | Source | Description |
|-------|--------|-------------|
| `DocDate` | `ProductionRun.date` | Posting date in YYYY-MM-DD format |
| `Comments` | Auto-generated | `"Production Execution — DocEntry {sap_doc_entry}"` |
| `DocumentLines[0].ItemCode` | Fetched from SAP `OWOR` header | Finished goods item code |
| `DocumentLines[0].Quantity` | `total_production - rejected_qty` | Net accepted production quantity |
| `DocumentLines[0].WarehouseCode` | Fetched from SAP `OWOR` header | Target warehouse for finished goods |
| `DocumentLines[0].BaseType` | Hardcoded `202` | SAP object type for Production Order |
| `DocumentLines[0].BaseEntry` | `ProductionRun.sap_doc_entry` | Links receipt to the SAP production order |
| `DocumentLines[0].BaseLine` | Hardcoded `0` | First line of the production order |

#### Flow Sequence

1. Operator calls `POST /api/production-execution/runs/<run_id>/complete/` with `{"total_production": 500}`
2. `complete_run()` validates the run, marks status as `COMPLETED`
3. If `sap_doc_entry` exists, fetches `ItemCode` and `Warehouse` from SAP `OWOR` table
4. Calculates net quantity: `total_production - rejected_qty`
5. Builds payload and posts to `POST /b1s/v2/InventoryGenEntries`
6. On success: saves returned `DocEntry` to `sap_receipt_doc_entry`, sets `sap_sync_status = SUCCESS`
7. On failure: sets `sap_sync_status = FAILED`, stores error in `sap_sync_error`

#### SAP Authentication (Service Layer)

```
POST /b1s/v2/Login
{
  "CompanyDB": "<company_db>",
  "UserName": "<username>",
  "Password": "<password>"
}
```

Session cookie is used for subsequent requests.

#### Retry Mechanism

If posting fails, the operator can retry via:

```
POST /api/production-execution/runs/<run_id>/retry-sap-receipt/
```

This calls `retry_sap_goods_receipt()` which re-attempts the same posting flow.

#### Database Tracking Fields (ProductionRun Model)

| Field | Type | Values |
|-------|------|--------|
| `sap_doc_entry` | IntegerField | SAP Production Order DocEntry (input link) |
| `sap_receipt_doc_entry` | IntegerField | SAP Goods Receipt DocEntry (output result) |
| `sap_sync_status` | CharField | `NOT_APPLICABLE`, `PENDING`, `SUCCESS`, `FAILED` |
| `sap_sync_error` | TextField | Error message if posting fails |

---

### 1.2 Production Order Creation (Available, Not Currently Used)

A writer exists for creating production orders directly in SAP, but is not currently called from the production execution workflow.

| Property | Description |
|----------|-------------|
| **SAP Endpoint** | `POST /b1s/v2/ProductionOrders` |
| **Writer Class** | `ProductionOrderWriter` in `sap_client/service_layer/production_order_writer.py` |

#### Payload Fields

| Field | Type | Description |
|-------|------|-------------|
| `ItemNo` | String | Finished product ItemCode |
| `PlannedQuantity` | Float | Total planned quantity |
| `DueDate` | String (YYYY-MM-DD) | Due date |
| `StartDate` | String (optional) | Start date |
| `Warehouse` | String (optional) | Production warehouse |
| `Remarks` | String (optional) | Remarks |
| `ProductionOrderStatus` | String (optional) | `boposPlanned` or `boposReleased` |
| `ProductionOrderLines[].ItemNo` | String | BOM component ItemCode |
| `ProductionOrderLines[].PlannedQuantity` | Float | Component planned qty |
| `ProductionOrderLines[].Warehouse` | String (optional) | Component warehouse |

---

## 2. Data Fetched FROM SAP

All read operations use **direct SAP HANA SQL queries** via `hdbcli`.

**Reader Class:** `ProductionOrderReader` in `production_execution/services/sap_reader.py`

---

### 2.1 Released Production Orders List

| Property | Description |
|----------|-------------|
| **App Endpoint** | `GET /api/production-execution/sap/orders/` |
| **View** | `SAPProductionOrderListAPI` |
| **Reader Method** | `get_released_production_orders()` |
| **SAP Table** | `OWOR` (Production Orders) |

#### SQL Query

```sql
SELECT
    W."DocEntry",
    W."DocNum",
    W."ItemCode",
    W."ProdName",
    W."PlannedQty",
    W."CmpltQty",
    W."RjctQty",
    (W."PlannedQty" - W."CmpltQty" - W."RjctQty") AS "RemainingQty",
    W."StartDate",
    W."DueDate",
    W."Warehouse",
    W."Status"
FROM "schema"."OWOR" W
WHERE W."Status" = 'R'
  AND (W."PlannedQty" - W."CmpltQty" - W."RjctQty") > 0
ORDER BY W."DueDate" ASC
```

#### Fields Returned

| Field | Type | Description |
|-------|------|-------------|
| `DocEntry` | Integer | SAP primary key |
| `DocNum` | String | Document number |
| `ItemCode` | String | Finished product code |
| `ProdName` | String | Product name |
| `PlannedQty` | Decimal | Total planned quantity |
| `CmpltQty` | Decimal | Already completed quantity |
| `RjctQty` | Decimal | Rejected quantity |
| `RemainingQty` | Decimal | `PlannedQty - CmpltQty - RjctQty` |
| `StartDate` | Date | Production start date |
| `DueDate` | Date | Production due date |
| `Warehouse` | String | Target warehouse code |
| `Status` | String | `R` = Released |

**Filter:** Only released orders (`Status = 'R'`) with remaining quantity > 0.

---

### 2.2 Production Order Detail with Components

| Property | Description |
|----------|-------------|
| **App Endpoint** | `GET /api/production-execution/sap/orders/<doc_entry>/` |
| **View** | `SAPProductionOrderDetailAPI` |
| **Reader Method** | `get_production_order_detail()` |
| **SAP Tables** | `OWOR` (Header) + `WOR1` (Components) |

#### Header: Same fields as 2.1

#### Components SQL Query (WOR1)

```sql
SELECT
    C."ItemCode",
    C."ItemName",
    C."PlannedQty",
    C."IssuedQty",
    C."wareHouse" AS "Warehouse",
    C."UomCode"
FROM "schema"."WOR1" C
WHERE C."DocEntry" = {doc_entry}
```

#### Component Fields

| Field | Type | Description |
|-------|------|-------------|
| `ItemCode` | String | Raw material item code |
| `ItemName` | String | Material name |
| `PlannedQty` | Decimal | Quantity needed for production |
| `IssuedQty` | Decimal | Quantity already issued from warehouse |
| `Warehouse` | String | Source warehouse |
| `UomCode` | String | Unit of measure |

---

### 2.3 Item Search

| Property | Description |
|----------|-------------|
| **App Endpoint** | `GET /api/production-execution/sap/items/?search=<query>` |
| **View** | `SAPItemSearchAPI` |
| **Reader Method** | `search_items()` |
| **SAP Table** | `OITM` (Item Master) |

#### SQL Query

```sql
SELECT TOP 50
    T0."ItemCode",
    T0."ItemName",
    T0."InvntryUom" AS "UomCode"
FROM "schema"."OITM" T0
WHERE T0."ItemCode" LIKE '%query%'
   OR T0."ItemName" LIKE '%query%'
ORDER BY T0."ItemName" ASC
```

#### Fields Returned

| Field | Type | Description |
|-------|------|-------------|
| `ItemCode` | String | Item code |
| `ItemName` | String | Item name |
| `UomCode` | String | Inventory unit of measure |

**Parameters:** `search` (min 2 chars), returns max 50 results.

---

### 2.4 BOM (Bill of Materials) by Item Code

| Property | Description |
|----------|-------------|
| **App Endpoint** | `GET /api/production-execution/sap/bom/?item_code=<code>` |
| **View** | `SAPItemBOMAPI` |
| **Reader Method** | `get_bom_by_item_code()` |
| **SAP Tables** | `OITT` (BOM Header) + `ITT1` (BOM Lines) + `OITM` (Item Master) |

#### SQL Query

```sql
SELECT
    T1."Code"      AS "ItemCode",
    T1."ItemName"  AS "ItemName",
    T1."Quantity"  AS "PlannedQty",
    COALESCE(T1."Uom", I."InvntryUom") AS "UomCode",
    T1."Warehouse" AS "Warehouse"
FROM "schema"."OITT" T0
INNER JOIN "schema"."ITT1" T1 ON T0."Code" = T1."Father"
LEFT JOIN "schema"."OITM" I ON T1."Code" = I."ItemCode"
WHERE T0."Code" = '{item_code}'
ORDER BY T1."VisOrder" ASC
```

#### Fields Returned

| Field | Type | Description |
|-------|------|-------------|
| `ItemCode` | String | Component raw material code |
| `ItemName` | String | Component name |
| `PlannedQty` | Decimal | Quantity per unit of finished goods |
| `UomCode` | String | Unit of measure (BOM UOM or inventory UOM fallback) |
| `Warehouse` | String | Default warehouse for the component |

#### Response Format

```json
{
  "item_code": "FG-001",
  "component_count": 3,
  "components": [
    {
      "ItemCode": "RM-001",
      "ItemName": "Raw Material 1",
      "PlannedQty": 10.0,
      "UomCode": "KG",
      "Warehouse": "WH-01"
    }
  ]
}
```

---

### 2.5 BOM Components for Production Run (Auto-Fetch)

| Property | Description |
|----------|-------------|
| **Reader Method** | `get_bom_components_for_run()` |
| **Called By** | `auto_populate_materials_from_bom()` in `ProductionExecutionService` |

#### Priority Logic

1. If `sap_doc_entry` is provided → Fetch components from `WOR1` (production order-specific BOM)
2. Else if `item_code` is provided → Fetch from `OITT/ITT1` (item master BOM)

When a production run is created and no manual materials are provided, BOM components are auto-populated as `ProductionMaterialUsage` records.

---

## 3. API Routes Summary

| Method | Route | Name | Purpose |
|--------|-------|------|---------|
| POST | `/api/production-execution/runs/` | `pe-run-list-create` | Create production run |
| GET | `/api/production-execution/runs/` | `pe-run-list-create` | List production runs |
| POST | `/api/production-execution/runs/<id>/complete/` | `pe-run-complete` | Complete run & post goods receipt to SAP |
| POST | `/api/production-execution/runs/<id>/retry-sap-receipt/` | `pe-run-retry-sap` | Retry failed SAP goods receipt |
| GET | `/api/production-execution/sap/orders/` | `pe-sap-orders` | List released SAP production orders |
| GET | `/api/production-execution/sap/orders/<id>/` | `pe-sap-order-detail` | Get production order detail + components |
| GET | `/api/production-execution/sap/items/?search=` | `pe-sap-items` | Search SAP item master |
| GET | `/api/production-execution/sap/bom/?item_code=` | `pe-sap-item-bom` | Get BOM components for an item |

---

## 4. SAP Tables Used

| SAP Table | Description | Used For |
|-----------|-------------|----------|
| `OWOR` | Production Orders | Read order header (list & detail) |
| `WOR1` | Production Order Components | Read BOM lines per order |
| `OITT` | Bill of Materials Header | Read master BOM |
| `ITT1` | Bill of Materials Lines | Read master BOM components |
| `OITM` | Item Master | Item search, UOM fallback |
| `OIGN` | Goods Receipt (Inventory Gen Entry) | Write goods receipt via Service Layer |

---

## 5. Error Handling

| Exception | When |
|-----------|------|
| `SAPReadError` | HANA SQL query fails |
| `SAPWriteError` | Service Layer POST fails |
| `SAPConnectionError` | Cannot connect to HANA or Service Layer |
| `SAPDataError` | Data not found or unexpected format |
| `SAPValidationError` | Payload validation failure |

All errors are captured in the `sap_sync_error` field on the `ProductionRun` model, and the `sap_sync_status` is set to `FAILED`.

---

## 6. Key Files

| File | Purpose |
|------|---------|
| `production_execution/services/sap_reader.py` | All SAP HANA read operations |
| `production_execution/services/sap_writer.py` | Goods receipt posting to Service Layer |
| `production_execution/services/production_service.py` | Business logic orchestration |
| `production_execution/views.py` | API views / endpoints |
| `production_execution/urls.py` | URL routing |
| `production_execution/models.py` | ProductionRun model with SAP fields |
| `production_execution/serializers.py` | API serializers |
| `sap_client/service_layer/production_order_writer.py` | Production order creation (unused) |
| `sap_client/client.py` | SAP client entry point |
