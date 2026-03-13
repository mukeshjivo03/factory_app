# SAP Plan Dashboard — API Reference

**Base URL:** `/api/v1/sap/plan-dashboard/`
**Authentication:** JWT Bearer token required on every request.
**Company Context:** `Company-Code` header required on every request.

---

## Authentication Headers

Every request must include:

```
Authorization: Bearer <access_token>
Company-Code: <company_code>
```

| Header | Required | Example |
|--------|----------|---------|
| `Authorization` | Yes | `Bearer eyJhbGci...` |
| `Company-Code` | Yes | `JIVO_OIL` |

---

## Common Query Parameters

All four endpoints share the same optional query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | `planned` \| `released` \| `all` | `all` | Filter by production order status |
| `due_date_from` | `YYYY-MM-DD` | — | Include orders with DueDate ≥ this date |
| `due_date_to` | `YYYY-MM-DD` | — | Include orders with DueDate ≤ this date |
| `warehouse` | string (max 8) | — | Filter by warehouse code (e.g. `WH-01`) |
| `sku` | string (max 50) | — | Filter by finished-good item code (e.g. `FG-001`) |
| `show_shortfall_only` | `true` \| `false` | `false` | Return only items/orders that have a shortfall |

**Validation rules:**
- `due_date_from` must be ≤ `due_date_to` when both are provided.
- `status` must be one of `planned`, `released`, `all`; any other value returns 400.

---

## Endpoints

---

### 1. `GET /summary/`

Returns one row per open production order with aggregated component shortfall counts.

**Permission required:** `sap_plan_dashboard.can_view_plan_dashboard`

#### Example Request

```
GET /api/v1/sap/plan-dashboard/summary/?status=planned&due_date_from=2026-03-01
Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Success Response — `200 OK`

```json
{
  "data": [
    {
      "prod_order_entry": 1234,
      "prod_order_num": 56,
      "sku_code": "FG-001",
      "sku_name": "Protein Bar 30g",
      "planned_qty": 500.0,
      "completed_qty": 0.0,
      "status": "planned",
      "due_date": "2026-03-20",
      "post_date": "2026-03-13",
      "priority": 2,
      "warehouse": "WH-01",
      "total_components": 8,
      "components_with_shortfall": 3,
      "total_remaining_component_qty": 875.0
    }
  ],
  "meta": {
    "total_orders": 12,
    "orders_with_shortfall": 5,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `prod_order_entry` | int | SAP B1 DocEntry (internal key) |
| `prod_order_num` | int | User-visible production order number |
| `sku_code` | string | Finished good item code |
| `sku_name` | string | Finished good description |
| `planned_qty` | float | Total planned production quantity |
| `completed_qty` | float | Already completed quantity |
| `status` | string | `planned` or `released` |
| `due_date` | string (YYYY-MM-DD) | Target completion date |
| `post_date` | string (YYYY-MM-DD) | Document posting date |
| `priority` | int | Order priority |
| `warehouse` | string | Default warehouse code |
| `total_components` | int | Total number of BOM component lines |
| `components_with_shortfall` | int | Count of components where stock < required |
| `total_remaining_component_qty` | float | Sum of (planned − issued) across all component lines |

---

### 2. `GET /details/`

Full BOM explosion for all open production orders. Returns production orders grouped with their component lines. Each component shows stock levels and shortfall.

**Permission required:** `sap_plan_dashboard.can_view_plan_dashboard`

#### Example Request

```
GET /api/v1/sap/plan-dashboard/details/?show_shortfall_only=true
Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Success Response — `200 OK`

```json
{
  "data": [
    {
      "prod_order_entry": 1234,
      "prod_order_num": 56,
      "sku_code": "FG-001",
      "sku_name": "Protein Bar 30g",
      "sku_planned_qty": 500.0,
      "sku_completed_qty": 0.0,
      "status": "planned",
      "due_date": "2026-03-20",
      "post_date": "2026-03-13",
      "warehouse": "WH-01",
      "priority": 2,
      "total_components": 8,
      "components_with_shortfall": 3,
      "components": [
        {
          "component_line": 0,
          "component_code": "RM-042",
          "component_name": "Oat Flour",
          "component_planned_qty": 125.0,
          "component_issued_qty": 0.0,
          "component_remaining_qty": 125.0,
          "component_warehouse": "RM-WH",
          "base_qty": 0.25,
          "uom": "KG",
          "stock_on_hand": 300.0,
          "stock_committed": 80.0,
          "stock_on_order": 200.0,
          "net_available": 220.0,
          "shortfall_qty": 0.0,
          "vendor_lead_time": 7,
          "default_vendor": "V-001",
          "stock_status": "sufficient"
        },
        {
          "component_line": 1,
          "component_code": "RM-043",
          "component_name": "Whey Protein",
          "component_planned_qty": 50.0,
          "component_issued_qty": 20.0,
          "component_remaining_qty": 30.0,
          "component_warehouse": "RM-WH",
          "base_qty": 0.1,
          "uom": "KG",
          "stock_on_hand": 10.0,
          "stock_committed": 5.0,
          "stock_on_order": 0.0,
          "net_available": 5.0,
          "shortfall_qty": 25.0,
          "vendor_lead_time": 14,
          "default_vendor": "V-002",
          "stock_status": "partial"
        }
      ]
    }
  ],
  "meta": {
    "total_orders": 12,
    "total_component_lines": 96,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

#### Component Fields

| Field | Type | Description |
|-------|------|-------------|
| `component_line` | int | Line number within the production order |
| `component_code` | string | Component item code |
| `component_name` | string | Component item name |
| `component_planned_qty` | float | Total planned qty of this component for the order |
| `component_issued_qty` | float | Qty already issued to production floor |
| `component_remaining_qty` | float | `planned − issued` |
| `component_warehouse` | string | Source warehouse for this component |
| `base_qty` | float | Qty per unit of parent (from BOM) |
| `uom` | string | Unit of measure |
| `stock_on_hand` | float | Total on-hand across all warehouses (OITM.OnHand) |
| `stock_committed` | float | Committed to other orders (OITM.IsCommited) |
| `stock_on_order` | float | Incoming on purchase order (OITM.OnOrder) |
| `net_available` | float | `OnHand − IsCommited` |
| `shortfall_qty` | float | `max(0, remaining_required − net_available)` |
| `vendor_lead_time` | int | Vendor lead time in days |
| `default_vendor` | string | Default vendor card code |
| `stock_status` | string | `sufficient` / `partial` / `stockout` (see below) |

**`stock_status` values:**

| Value | Condition |
|-------|-----------|
| `sufficient` | `net_available >= component_remaining_qty` |
| `partial` | `0 < net_available < component_remaining_qty` |
| `stockout` | `net_available <= 0` |

---

### 3. `GET /procurement/`

Aggregated view for the purchasing team. One row per component across ALL open production orders. Sorted by `shortfall_qty` descending (worst first).

**Permission required:** `sap_plan_dashboard.can_view_plan_dashboard`

#### Example Request

```
GET /api/v1/sap/plan-dashboard/procurement/?show_shortfall_only=true
Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Success Response — `200 OK`

```json
{
  "data": [
    {
      "component_code": "RM-043",
      "component_name": "Whey Protein",
      "uom": "KG",
      "total_required_qty": 250.0,
      "stock_on_hand": 10.0,
      "stock_committed": 5.0,
      "stock_on_order": 0.0,
      "net_available": 5.0,
      "shortfall_qty": 245.0,
      "suggested_purchase_qty": 245.0,
      "vendor_lead_time": 14,
      "default_vendor": "V-002",
      "related_prod_orders": ["56", "57", "60"]
    }
  ],
  "meta": {
    "total_components": 45,
    "components_with_shortfall": 12,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `component_code` | string | Component item code |
| `component_name` | string | Component item name |
| `uom` | string | Inventory unit of measure |
| `total_required_qty` | float | Sum of (planned−issued) across ALL open orders |
| `stock_on_hand` | float | Current on-hand (from OITM) |
| `stock_committed` | float | Already committed to other orders |
| `stock_on_order` | float | Incoming on purchase orders |
| `net_available` | float | `OnHand − IsCommited` |
| `shortfall_qty` | float | `max(0, total_required − net_available)` |
| `suggested_purchase_qty` | float | Same as `shortfall_qty` (add your safety buffer on the frontend) |
| `vendor_lead_time` | int | Lead time in days |
| `default_vendor` | string | Default vendor card code |
| `related_prod_orders` | string[] | Production order numbers that need this component |

> **Note:** `suggested_purchase_qty` equals `shortfall_qty`. Apply a safety buffer on the frontend if needed (e.g. `shortfall_qty * 1.1` for 10% buffer).

---

### 4. `GET /sku/<doc_entry>/`

Full component detail for a single production order. Same data as `/details/` but for one order only, structured as a single object.

**Permission required:** `sap_plan_dashboard.can_view_plan_dashboard`

**Path parameter:** `doc_entry` — SAP B1 internal DocEntry integer.

#### Example Request

```
GET /api/v1/sap/plan-dashboard/sku/1234/
Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Success Response — `200 OK`

```json
{
  "data": {
    "prod_order_entry": 1234,
    "prod_order_num": 56,
    "sku_code": "FG-001",
    "sku_name": "Protein Bar 30g",
    "sku_planned_qty": 500.0,
    "sku_completed_qty": 0.0,
    "status": "planned",
    "due_date": "2026-03-20",
    "post_date": "2026-03-13",
    "warehouse": "WH-01",
    "priority": 2,
    "total_components": 8,
    "components_with_shortfall": 3,
    "components": [ /* same shape as /details/ components */ ]
  },
  "meta": {
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

#### Error Response — `404 Not Found`

Returned when the `doc_entry` does not exist or the production order is not in Planned/Released status.

```json
{
  "detail": "Production order 9999 not found or is not in Planned/Released status."
}
```

---

## Error Responses

All endpoints return a consistent error shape.

### 400 Bad Request — Invalid Query Parameters

```json
{
  "detail": "Invalid query parameters.",
  "errors": {
    "status": ["\"completed\" is not a valid choice."],
    "due_date_from": ["Date has wrong format. Use one of these formats instead: YYYY-MM-DD."]
  }
}
```

### 401 Unauthorized — Missing or Invalid Token

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden — Missing Company-Code Header or No Permission

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found — SKU Detail Endpoint Only

```json
{
  "detail": "Production order 9999 not found or is not in Planned/Released status."
}
```

### 502 Bad Gateway — SAP Data Error

Returned when the HANA query executes but returns an error (invalid SQL, schema mismatch).

```json
{
  "detail": "SAP data error: Failed to retrieve plan dashboard data from SAP. Invalid query."
}
```

### 503 Service Unavailable — SAP Connection Error

Returned when the HANA database is unreachable.

```json
{
  "detail": "SAP system is currently unavailable. Please try again later."
}
```

---

## Permission Setup

Add these custom permissions to a user's profile via Django admin or the `/api/v1/company/` endpoints:

| Permission codename | Description |
|---------------------|-------------|
| `can_view_plan_dashboard` | View all plan dashboard endpoints |
| `can_export_plan_dashboard` | Reserved for future CSV/Excel export endpoint |

---

## Calculation Reference

| Field | Formula |
|-------|---------|
| `component_remaining_qty` | `WOR1.PlannedQty − WOR1.IssuedQty` |
| `net_available` | `OITM.OnHand − OITM.IsCommited` |
| `shortfall_qty` | `max(0, component_remaining_qty − net_available)` |
| `suggested_purchase_qty` | `shortfall_qty` (apply safety buffer on frontend) |
| `total_required_qty` (procurement) | `SUM(component_remaining_qty)` for the same item across all orders |
| `shortfall_qty` (procurement) | `max(0, total_required_qty − net_available)` |

---

## Data Source

All data is read live from SAP B1 HANA on every request. There is no local caching layer currently. Consider adding client-side caching (e.g. React Query `staleTime`) to avoid unnecessary round-trips.

SAP B1 tables used:

| Table | Purpose |
|-------|---------|
| `OWOR` | Production orders |
| `WOR1` | BOM component lines per order |
| `OITM` | Item master — stock levels, vendor, UoM |
| `OCRD` | Business partners (vendor names) — not currently in responses |
