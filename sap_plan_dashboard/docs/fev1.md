# SAP Plan Dashboard — Frontend Developer Reference v1

> **Audience:** Frontend engineers integrating the Plan Dashboard.
> **Backend:** Django REST Framework · SAP HANA (live data)
> **Base path:** `/api/v1/sap/plan-dashboard/`
> **Auth:** JWT Bearer · Company-Code header

---

## Table of Contents

1. [Quick Start Checklist](#1-quick-start-checklist)
2. [Authentication & Headers](#2-authentication--headers)
3. [Endpoints at a Glance](#3-endpoints-at-a-glance)
4. [Endpoint 1 — GET /summary/](#4-endpoint-1--get-summary)
5. [Endpoint 2 — GET /details/](#5-endpoint-2--get-details)
6. [Endpoint 3 — GET /procurement/](#6-endpoint-3--get-procurement)
7. [Endpoint 4 — GET /sku/\<doc\_entry\>/](#7-endpoint-4--get-skudoc_entry)
8. [Query Parameters (All Endpoints)](#8-query-parameters-all-endpoints)
9. [HTTP Status Codes](#9-http-status-codes)
10. [Error Response Reference](#10-error-response-reference)
11. [Field Glossary](#11-field-glossary)
12. [Calculation Logic](#12-calculation-logic)
13. [TypeScript Types](#13-typescript-types)
14. [Axios Setup](#14-axios-setup)
15. [React Query Hooks](#15-react-query-hooks)
16. [UI Rules & Display Logic](#16-ui-rules--display-logic)
17. [Edge Cases & Gotchas](#17-edge-cases--gotchas)
18. [Permissions](#18-permissions)
19. [Change Log](#19-change-log)

---

## 1. Quick Start Checklist

Before making your first API call, confirm you have:

- [ ] `access` JWT token from `POST /api/v1/accounts/login/`
- [ ] `Company-Code` value from the login response (`companies[].code`)
- [ ] User has `can_view_plan_dashboard` permission (ask backend/admin team if getting 403)
- [ ] Axios base URL configured and both headers set as defaults

---

## 2. Authentication & Headers

### 2.1 How to Get a Token

```
POST /api/v1/accounts/login/
Content-Type: application/json
```

**Request body:**
```json
{
  "email": "planner@company.com",
  "password": "yourpassword"
}
```

**Response — 200 OK:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3....",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3....",
  "user": {
    "id": 1,
    "email": "planner@company.com",
    "full_name": "John Doe"
  },
  "companies": [
    {
      "code": "JIVO_OIL",
      "name": "Jivo Oil",
      "role": "Planner",
      "is_default": true
    },
    {
      "code": "JIVO_MART",
      "name": "Jivo Mart",
      "role": "Viewer",
      "is_default": false
    }
  ]
}
```

> **Token lifetime:** `access` token is valid for **25 hours**. `refresh` token is valid for **7 days**.

### 2.2 Refresh a Token

```
POST /api/v1/accounts/token/refresh/
Content-Type: application/json
```

**Request body:**
```json
{ "refresh": "<refresh_token>" }
```

**Response — 200 OK:**
```json
{
  "access": "eyJhbGciOiJIUzI...",
  "refresh": "eyJhbGciOiJIUzI..."
}
```

> Refresh tokens rotate on every use — store the new `refresh` token each time.

### 2.3 Required Headers on Every Request

Every plan dashboard API call **must** include both of these headers. Without them you will get a `401` or `403`.

```
Authorization: Bearer <access_token>
Company-Code: JIVO_OIL
```

| Header | Required | Value |
|--------|----------|-------|
| `Authorization` | **Yes** | `Bearer ` + access token string |
| `Company-Code` | **Yes** | Company code from login response (`companies[].code`) |
| `Content-Type` | No | Not needed for GET requests |

### 2.4 What Happens If Headers Are Missing

| Scenario | Status | Error Message |
|----------|--------|---------------|
| No `Authorization` header | `401` | `"Authentication credentials were not provided."` |
| Expired or invalid token | `401` | `"Given token not valid for any token type"` |
| No `Company-Code` header | `403` | `"You do not have permission to perform this action."` |
| Invalid company code | `403` | `"You do not have permission to perform this action."` |

---

## 3. Endpoints at a Glance

| # | Method | URL | Use Case | Response `data` shape |
|---|--------|-----|----------|-----------------------|
| 1 | GET | `/summary/` | SKU summary table | `Array<SummaryOrder>` |
| 2 | GET | `/details/` | Full BOM explosion | `Array<DetailOrder>` (with nested `components[]`) |
| 3 | GET | `/procurement/` | Purchase requirements | `Array<ProcurementItem>` |
| 4 | GET | `/sku/<doc_entry>/` | Single order detail panel | `SKUDetailData` (single object, not array) |

All endpoints:
- Accept the same query parameters (see [Section 8](#8-query-parameters-all-endpoints))
- Return data live from SAP HANA (no server cache)
- Only return `Status IN ('P', 'R')` — Planned and Released orders
- Are read-only (GET only, no POST/PUT/DELETE)

---

## 4. Endpoint 1 — GET /summary/

**URL:** `GET /api/v1/sap/plan-dashboard/summary/`

Returns **one row per production order** with counts of shortfall components. Use this to build the main SKU table and the summary stat cards.

### 4.1 Request

```
GET /api/v1/sap/plan-dashboard/summary/?status=planned&due_date_from=2026-03-01
Authorization: Bearer eyJhbGci...
Company-Code: JIVO_OIL
```

No request body. All filters are query parameters.

### 4.2 Success Response — `200 OK`

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
    },
    {
      "prod_order_entry": 1235,
      "prod_order_num": 57,
      "sku_code": "FG-002",
      "sku_name": "Oat Granola 500g",
      "planned_qty": 200.0,
      "completed_qty": 50.0,
      "status": "released",
      "due_date": "2026-03-22",
      "post_date": "2026-03-10",
      "priority": 1,
      "warehouse": "WH-02",
      "total_components": 5,
      "components_with_shortfall": 0,
      "total_remaining_component_qty": 320.5
    }
  ],
  "meta": {
    "total_orders": 2,
    "orders_with_shortfall": 1,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

### 4.3 Response Field Definitions

#### `data[]` — Array of production orders

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `prod_order_entry` | `number` | No | SAP internal DocEntry — use as key for `/sku/<doc_entry>/` |
| `prod_order_num` | `number` | No | User-visible order number — show as "PO-56" |
| `sku_code` | `string` | No | Finished good item code (e.g. `"FG-001"`) |
| `sku_name` | `string` | No | Finished good description |
| `planned_qty` | `number` | No | Total planned production quantity |
| `completed_qty` | `number` | No | Already completed quantity |
| `status` | `"planned" \| "released"` | No | Production order status |
| `due_date` | `string` (YYYY-MM-DD) | **Yes** | Target completion date — can be `null` |
| `post_date` | `string` (YYYY-MM-DD) | **Yes** | Document posting date — can be `null` |
| `priority` | `number` | No | SAP priority (0 = normal, higher = more urgent) |
| `warehouse` | `string` | No | Default warehouse code for this order |
| `total_components` | `number` | No | Total number of BOM component lines |
| `components_with_shortfall` | `number` | No | How many components have insufficient stock |
| `total_remaining_component_qty` | `number` | No | Sum of (planned − issued) across all component lines |

#### `meta` — Response metadata

| Field | Type | Description |
|-------|------|-------------|
| `total_orders` | `number` | Total orders returned (after filters) |
| `orders_with_shortfall` | `number` | Orders where at least one component is short |
| `fetched_at` | `string` (ISO 8601) | UTC timestamp when data was fetched from SAP |

### 4.4 Empty State

When no orders match the filters, `data` is an empty array — not an error:

```json
{
  "data": [],
  "meta": {
    "total_orders": 0,
    "orders_with_shortfall": 0,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

---

## 5. Endpoint 2 — GET /details/

**URL:** `GET /api/v1/sap/plan-dashboard/details/`

Returns all production orders with their **nested BOM component lines**. Each component includes real-time stock levels and calculated shortfall. This is a heavier call than `/summary/`.

> **Performance tip:** Prefer using `/sku/<doc_entry>/` to load one order at a time (on row expand), rather than `/details/` which loads everything at once.

### 5.1 Request

```
GET /api/v1/sap/plan-dashboard/details/?show_shortfall_only=true
Authorization: Bearer eyJhbGci...
Company-Code: JIVO_OIL
```

### 5.2 Success Response — `200 OK`

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
        },
        {
          "component_line": 2,
          "component_code": "PKG-010",
          "component_name": "Wrapper Foil",
          "component_planned_qty": 500.0,
          "component_issued_qty": 0.0,
          "component_remaining_qty": 500.0,
          "component_warehouse": "PKG-WH",
          "base_qty": 1.0,
          "uom": "PC",
          "stock_on_hand": 0.0,
          "stock_committed": 0.0,
          "stock_on_order": 1000.0,
          "net_available": 0.0,
          "shortfall_qty": 500.0,
          "vendor_lead_time": 3,
          "default_vendor": "V-010",
          "stock_status": "stockout"
        }
      ]
    }
  ],
  "meta": {
    "total_orders": 1,
    "total_component_lines": 3,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

### 5.3 Response Field Definitions

#### `data[]` — Order-level fields (same as summary, plus `components`)

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `prod_order_entry` | `number` | No | SAP internal DocEntry |
| `prod_order_num` | `number` | No | User-visible order number |
| `sku_code` | `string` | No | Finished good item code |
| `sku_name` | `string` | No | Finished good description |
| `sku_planned_qty` | `number` | No | Total planned qty (note: field name differs from summary's `planned_qty`) |
| `sku_completed_qty` | `number` | No | Already completed qty (note: differs from summary's `completed_qty`) |
| `status` | `string` | No | `"planned"` or `"released"` |
| `due_date` | `string` | **Yes** | YYYY-MM-DD or `null` |
| `post_date` | `string` | **Yes** | YYYY-MM-DD or `null` |
| `warehouse` | `string` | No | Default warehouse code |
| `priority` | `number` | No | SAP priority |
| `total_components` | `number` | No | Total component line count |
| `components_with_shortfall` | `number` | No | Components with `shortfall_qty > 0` |
| `components` | `BOMComponent[]` | No | Array of BOM component lines (see below) |

#### `data[].components[]` — Component-level fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `component_line` | `number` | No | Line number within this production order (0-indexed) |
| `component_code` | `string` | No | Component item code |
| `component_name` | `string` | No | Component item name |
| `component_planned_qty` | `number` | No | Total planned qty of this component for this order |
| `component_issued_qty` | `number` | No | Already issued to the production floor |
| `component_remaining_qty` | `number` | No | `planned − issued` (how much still needs to be pulled) |
| `component_warehouse` | `string` | No | Source warehouse for this component (may be `""`) |
| `base_qty` | `number` | No | Qty per unit of parent SKU (from BOM master) |
| `uom` | `string` | No | Unit of measure (e.g. `"KG"`, `"PC"`, `"LTR"`) |
| `stock_on_hand` | `number` | No | Total stock across all warehouses (`OITM.OnHand`) |
| `stock_committed` | `number` | No | Reserved for other orders (`OITM.IsCommited`) |
| `stock_on_order` | `number` | No | Incoming on purchase orders (`OITM.OnOrder`) |
| `net_available` | `number` | No | `stock_on_hand − stock_committed` |
| `shortfall_qty` | `number` | No | `max(0, component_remaining_qty − net_available)` — never negative |
| `vendor_lead_time` | `number` | No | Vendor lead time in days (0 if not configured) |
| `default_vendor` | `string` | No | Default vendor card code (may be `""` if not set) |
| `stock_status` | `"sufficient" \| "partial" \| "stockout"` | No | Stock health label (see [Section 16.1](#161-stock-status-color-coding)) |

#### `meta`

| Field | Type | Description |
|-------|------|-------------|
| `total_orders` | `number` | Number of production orders returned |
| `total_component_lines` | `number` | Total BOM lines across all orders |
| `fetched_at` | `string` | UTC ISO 8601 timestamp |

### 5.4 Effect of `show_shortfall_only=true` on `/details/`

- Component lines where `shortfall_qty === 0` are **removed**.
- If an entire production order has zero shortfall on all components, the **entire order is removed** from `data`.
- `total_component_lines` in `meta` reflects only the returned (filtered) lines.

---

## 6. Endpoint 3 — GET /procurement/

**URL:** `GET /api/v1/sap/plan-dashboard/procurement/`

Returns **one aggregated row per component** across ALL open production orders. This is the purchasing team's view. Results are pre-sorted by `shortfall_qty` descending (worst first).

### 6.1 Request

```
GET /api/v1/sap/plan-dashboard/procurement/?show_shortfall_only=true
Authorization: Bearer eyJhbGci...
Company-Code: JIVO_OIL
```

### 6.2 Success Response — `200 OK`

```json
{
  "data": [
    {
      "component_code": "PKG-010",
      "component_name": "Wrapper Foil",
      "uom": "PC",
      "total_required_qty": 1200.0,
      "stock_on_hand": 0.0,
      "stock_committed": 0.0,
      "stock_on_order": 1000.0,
      "net_available": 0.0,
      "shortfall_qty": 1200.0,
      "suggested_purchase_qty": 1200.0,
      "vendor_lead_time": 3,
      "default_vendor": "V-010",
      "related_prod_orders": ["56", "57", "60"]
    },
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
      "related_prod_orders": ["56", "57"]
    },
    {
      "component_code": "RM-042",
      "component_name": "Oat Flour",
      "uom": "KG",
      "total_required_qty": 375.0,
      "stock_on_hand": 300.0,
      "stock_committed": 80.0,
      "stock_on_order": 200.0,
      "net_available": 220.0,
      "shortfall_qty": 155.0,
      "suggested_purchase_qty": 155.0,
      "vendor_lead_time": 7,
      "default_vendor": "V-001",
      "related_prod_orders": ["56"]
    }
  ],
  "meta": {
    "total_components": 3,
    "components_with_shortfall": 3,
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

### 6.3 Response Field Definitions

#### `data[]` — One row per unique component

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `component_code` | `string` | No | Component item code |
| `component_name` | `string` | No | Component item name |
| `uom` | `string` | No | Inventory unit of measure |
| `total_required_qty` | `number` | No | **Sum** of `component_remaining_qty` for this item across all open orders |
| `stock_on_hand` | `number` | No | Current on-hand stock (from SAP item master) |
| `stock_committed` | `number` | No | Already committed to other orders |
| `stock_on_order` | `number` | No | Incoming on purchase orders (for reference — not counted in shortfall) |
| `net_available` | `number` | No | `stock_on_hand − stock_committed` |
| `shortfall_qty` | `number` | No | `max(0, total_required_qty − net_available)` |
| `suggested_purchase_qty` | `number` | No | Same as `shortfall_qty` — apply safety buffer on frontend if needed |
| `vendor_lead_time` | `number` | No | Lead time in days (0 if not configured in SAP) |
| `default_vendor` | `string` | No | Default vendor card code (may be `""`) |
| `related_prod_orders` | `string[]` | No | Production order **numbers** (not DocEntry) that need this component |

> **Important:** `stock_on_order` is shown for information only. It is **not** subtracted from `shortfall_qty`. The calculation is: `shortfall = total_required − net_available`. The on-order stock represents future incoming supply that procurement should be aware of, but the dashboard conservatively shows what you need to buy today.

#### `meta`

| Field | Type | Description |
|-------|------|-------------|
| `total_components` | `number` | Unique components returned (after filters) |
| `components_with_shortfall` | `number` | Components where `shortfall_qty > 0` |
| `fetched_at` | `string` | UTC ISO 8601 timestamp |

### 6.4 Sort Order

Pre-sorted server-side:
1. `shortfall_qty` **descending** (worst first)
2. `total_required_qty` **descending** (tie-breaker)

You can re-sort on the frontend by any column, but the default sort shows the most critical items first.

---

## 7. Endpoint 4 — GET /sku/\<doc\_entry\>/

**URL:** `GET /api/v1/sap/plan-dashboard/sku/<doc_entry>/`

Returns the full detail for **one production order** — the order header plus all its BOM components. Use this on row expand or when opening a detail panel.

`<doc_entry>` is `prod_order_entry` (SAP's internal integer DocEntry) from the summary or details response.

### 7.1 Request

```
GET /api/v1/sap/plan-dashboard/sku/1234/
Authorization: Bearer eyJhbGci...
Company-Code: JIVO_OIL
```

No query parameters accepted (filters don't apply to this endpoint).

### 7.2 Success Response — `200 OK`

> **Important:** `data` is a **single object**, not an array. All other endpoints return `data` as an array.

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
    "total_components": 3,
    "components_with_shortfall": 2,
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
      },
      {
        "component_line": 2,
        "component_code": "PKG-010",
        "component_name": "Wrapper Foil",
        "component_planned_qty": 500.0,
        "component_issued_qty": 0.0,
        "component_remaining_qty": 500.0,
        "component_warehouse": "PKG-WH",
        "base_qty": 1.0,
        "uom": "PC",
        "stock_on_hand": 0.0,
        "stock_committed": 0.0,
        "stock_on_order": 1000.0,
        "net_available": 0.0,
        "shortfall_qty": 500.0,
        "vendor_lead_time": 3,
        "default_vendor": "V-010",
        "stock_status": "stockout"
      }
    ]
  },
  "meta": {
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

### 7.3 Error Response — `404 Not Found`

Returned when the `doc_entry` does not exist in SAP or the production order is Closed/Cancelled.

```json
{
  "detail": "Production order 9999 not found or is not in Planned/Released status."
}
```

---

## 8. Query Parameters (All Endpoints)

Applies to `/summary/`, `/details/`, and `/procurement/`. The `/sku/<doc_entry>/` endpoint does **not** accept query parameters.

### 8.1 Parameter Reference Table

| Parameter | Type | Default | Required | Validation |
|-----------|------|---------|----------|------------|
| `status` | string | `"all"` | No | Must be `planned`, `released`, or `all` |
| `due_date_from` | string | — | No | Format: `YYYY-MM-DD` |
| `due_date_to` | string | — | No | Format: `YYYY-MM-DD`; must be ≥ `due_date_from` |
| `warehouse` | string | — | No | Max 8 characters |
| `sku` | string | — | No | Max 50 characters |
| `show_shortfall_only` | boolean | `false` | No | Send as `"true"` or `"false"` string |

### 8.2 Parameter Details

**`status`**

| Value | Meaning |
|-------|---------|
| `"all"` (default) | Include both Planned and Released orders |
| `"planned"` | Only orders in Planned state (not yet started) |
| `"released"` | Only orders in Released state (production started) |

**`due_date_from` and `due_date_to`**

Both are optional. Can be used independently or together.

```
?due_date_from=2026-03-01              # all orders due on/after March 1
?due_date_to=2026-03-31                # all orders due on/before March 31
?due_date_from=2026-03-01&due_date_to=2026-03-31   # March only
```

If `due_date_from > due_date_to`, the server returns `400`:
```json
{
  "detail": "Invalid query parameters.",
  "errors": {
    "non_field_errors": ["due_date_from must be before or equal to due_date_to."]
  }
}
```

**`warehouse`**

Filters production orders by their **header warehouse** (the order's default warehouse, `OWOR.Warehouse`). This is not the component warehouse. Leave blank to see all warehouses.

**`sku`**

Filters to show only orders for a specific finished good. Pass the exact item code as it appears in SAP (e.g. `FG-001`). Case-sensitive.

**`show_shortfall_only`**

| Endpoint | Effect |
|----------|--------|
| `/summary/` | Returns only orders where `components_with_shortfall > 0` |
| `/details/` | Removes shortfall-free component lines; orders with zero shortfall are fully removed |
| `/procurement/` | Returns only components where `shortfall_qty > 0` |

### 8.3 Sending Booleans as Query Params

```
?show_shortfall_only=true     ✅ works
?show_shortfall_only=false    ✅ works
?show_shortfall_only=1        ✅ works (truthy)
?show_shortfall_only=0        ✅ works (falsy)
?show_shortfall_only=True     ❌ fails — use lowercase
```

---

## 9. HTTP Status Codes

### Complete Status Code Reference

| Status Code | Name | When You See It | What to Do |
|-------------|------|-----------------|------------|
| `200 OK` | Success | Request succeeded | Render the `data` array |
| `400 Bad Request` | Validation Error | Invalid query params (bad date format, invalid status choice) | Show inline validation errors on the filter UI |
| `401 Unauthorized` | Auth Failed | Missing `Authorization` header, expired token, invalid token | Redirect to login or refresh the token |
| `403 Forbidden` | Permission Denied | Missing `Company-Code` header, invalid company code, or user lacks `can_view_plan_dashboard` permission | Show access denied message; do not retry |
| `404 Not Found` | Not Found | `/sku/<doc_entry>/` only — order doesn't exist or is Closed/Cancelled | Show "order not found" in the detail panel |
| `502 Bad Gateway` | SAP Query Error | SAP HANA returned a query or data error | Show "data error from SAP" banner; notify admin |
| `503 Service Unavailable` | SAP Unreachable | Cannot connect to SAP HANA server | Show retry banner with manual refresh button |

---

## 10. Error Response Reference

### 10.1 Standard Error Shape

All error responses use this shape:

```typescript
{
  detail: string;         // Human-readable error message
  errors?: {              // Only present on 400 validation errors
    [field: string]: string[];
  };
}
```

### 10.2 All Possible Error Bodies

**400 — Invalid status choice:**
```json
{
  "detail": "Invalid query parameters.",
  "errors": {
    "status": ["\"completed\" is not a valid choice."]
  }
}
```

**400 — Invalid date format:**
```json
{
  "detail": "Invalid query parameters.",
  "errors": {
    "due_date_from": ["Date has wrong format. Use one of these formats instead: YYYY-MM-DD."]
  }
}
```

**400 — Date range reversed:**
```json
{
  "detail": "Invalid query parameters.",
  "errors": {
    "non_field_errors": ["due_date_from must be before or equal to due_date_to."]
  }
}
```

**401 — No token:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**401 — Expired token:**
```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [
    {
      "token_class": "AccessToken",
      "token_type": "access",
      "message": "Token is expired"
    }
  ]
}
```

**403 — No company header or no permission:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**404 — Production order not found:**
```json
{
  "detail": "Production order 9999 not found or is not in Planned/Released status."
}
```

**502 — SAP query/data error:**
```json
{
  "detail": "SAP data error: Failed to retrieve plan dashboard data from SAP. Invalid query."
}
```

**503 — SAP unreachable:**
```json
{
  "detail": "SAP system is currently unavailable. Please try again later."
}
```

### 10.3 Recommended Error Handling Pattern

```typescript
async function handleApiError(error: AxiosError) {
  const status = error.response?.status;
  const detail = (error.response?.data as any)?.detail ?? "Unknown error";

  switch (status) {
    case 400:
      // Show field errors inline on the filter form
      const errors = (error.response?.data as any)?.errors;
      showFilterErrors(errors);
      break;

    case 401:
      // Try to refresh token first; if that fails, go to login
      const refreshed = await tryRefreshToken();
      if (!refreshed) redirectToLogin();
      break;

    case 403:
      showToast("Access denied. Check your company selection or contact admin.", "error");
      break;

    case 404:
      // Only happens on /sku/<doc_entry>/
      showInDetailPanel("Production order not found or no longer active.");
      break;

    case 502:
      showBanner("SAP returned an error. Contact your system administrator.", "error");
      break;

    case 503:
      showBanner("SAP is temporarily unavailable.", "warning", {
        action: "Retry",
        onAction: () => refetchCurrentQuery(),
      });
      break;

    default:
      showToast(`Unexpected error: ${detail}`, "error");
  }
}
```

---

## 11. Field Glossary

| Term | What It Means |
|------|--------------|
| `prod_order_entry` | SAP B1's internal `DocEntry` — an integer primary key. Use this in the URL for `/sku/<doc_entry>/`. Never display this to users. |
| `prod_order_num` | The user-visible production order number from SAP B1. Display as `"PO-56"` or just `"56"`. |
| `sku_code` / `sku` | The finished good (product) being manufactured. Comes from `OWOR.ItemCode`. |
| `component_code` | Raw material or packaging item used to make the SKU. Comes from `WOR1.ItemCode`. |
| `component_planned_qty` | How much of the component is needed for the full order according to the BOM explosion. |
| `component_issued_qty` | How much has already been physically pulled from the warehouse and given to production. |
| `component_remaining_qty` | `planned − issued` — what still needs to be pulled. This is the true demand figure. |
| `stock_on_hand` | Total inventory in all warehouses (`OITM.OnHand`). This is the gross figure. |
| `stock_committed` | Stock already reserved for other open orders (`OITM.IsCommited`). |
| `net_available` | `stock_on_hand − stock_committed` — what you can actually use for new demand. |
| `stock_on_order` | Items already on an open purchase order — incoming but not yet received. |
| `shortfall_qty` | How much you are short: `max(0, remaining_required − net_available)`. Never negative. |
| `suggested_purchase_qty` | Same as `shortfall_qty`. Add your safety buffer on the frontend. |
| `total_required_qty` | In procurement view only — the sum of `component_remaining_qty` for this item across ALL open orders. |
| `base_qty` | The ratio from the BOM master — how many units of this component go into 1 unit of the parent SKU. |
| `uom` | Unit of measure code (e.g. `"KG"`, `"PC"`, `"LTR"`, `"BOX"`). |
| `stock_status` | A computed label: `"sufficient"` / `"partial"` / `"stockout"`. Use for color coding. |
| `related_prod_orders` | In procurement view — the production order numbers (as strings) that need this component. |
| `vendor_lead_time` | Days from order to delivery for this item (from SAP item master). `0` means not configured. |
| `default_vendor` | The default SAP vendor card code for purchasing this item. May be `""` if not set. |
| `due_date` | When the production order must be completed. `null` if not set in SAP. |
| `post_date` | When the production order document was created in SAP. `null` if not set. |
| `priority` | SAP integer priority. Higher number = more urgent. `0` = normal priority. |
| `fetched_at` | UTC timestamp when the backend fetched this data from SAP HANA. |

---

## 12. Calculation Logic

Understanding how the backend computes these values helps you display them correctly and build features like safety-buffer calculation.

### 12.1 Core Formulas

```
component_remaining_qty  = component_planned_qty − component_issued_qty
net_available            = stock_on_hand − stock_committed
shortfall_qty            = max(0, component_remaining_qty − net_available)
```

### 12.2 Procurement Aggregation (for `/procurement/`)

```
total_required_qty  = SUM(component_remaining_qty)   for same item across all open orders
shortfall_qty       = max(0, total_required_qty − net_available)
suggested_purchase_qty = shortfall_qty
```

Note: `net_available` for procurement uses the item-master value (same regardless of which order is referencing it).

### 12.3 Stock Status Labels

```
if net_available >= component_remaining_qty  → "sufficient"
if net_available > 0                         → "partial"
if net_available <= 0                        → "stockout"
```

### 12.4 Safety Buffer (Frontend Responsibility)

The server returns `suggested_purchase_qty = shortfall_qty` with no buffer. If your purchasing team wants a buffer:

```typescript
const withBuffer = (qty: number, bufferPercent: number): number =>
  Math.ceil(qty * (1 + bufferPercent / 100));

// 10% safety buffer
const purchaseQty = withBuffer(item.suggested_purchase_qty, 10);
```

### 12.5 Completion Percentage (You Can Compute)

```typescript
const completionPct = (order.completed_qty / order.planned_qty) * 100;
// e.g. 100 / 500 = 20%
```

---

## 13. TypeScript Types

Copy these into your `types/sap-plan-dashboard.types.ts` file.

```typescript
// ─── Shared ──────────────────────────────────────────────────────────────────

export type ProductionOrderStatus = "planned" | "released";
export type StockStatus = "sufficient" | "partial" | "stockout";

// ─── BOM Component (used in /details/ and /sku/<id>/) ───────────────────────

export interface BOMComponent {
  component_line: number;
  component_code: string;
  component_name: string;
  component_planned_qty: number;
  component_issued_qty: number;
  component_remaining_qty: number;
  component_warehouse: string;         // may be ""
  base_qty: number;
  uom: string;
  stock_on_hand: number;
  stock_committed: number;
  stock_on_order: number;
  net_available: number;
  shortfall_qty: number;               // always >= 0
  vendor_lead_time: number;            // 0 = not configured
  default_vendor: string;              // may be ""
  stock_status: StockStatus;
}

// ─── /summary/ ───────────────────────────────────────────────────────────────

export interface SummaryOrder {
  prod_order_entry: number;
  prod_order_num: number;
  sku_code: string;
  sku_name: string;
  planned_qty: number;
  completed_qty: number;
  status: ProductionOrderStatus;
  due_date: string | null;             // "YYYY-MM-DD" or null
  post_date: string | null;            // "YYYY-MM-DD" or null
  priority: number;
  warehouse: string;
  total_components: number;
  components_with_shortfall: number;
  total_remaining_component_qty: number;
}

export interface SummaryMeta {
  total_orders: number;
  orders_with_shortfall: number;
  fetched_at: string;                  // ISO 8601 UTC
}

export interface SummaryResponse {
  data: SummaryOrder[];
  meta: SummaryMeta;
}

// ─── /details/ ───────────────────────────────────────────────────────────────

export interface DetailOrder {
  prod_order_entry: number;
  prod_order_num: number;
  sku_code: string;
  sku_name: string;
  sku_planned_qty: number;             // NOTE: different field name from SummaryOrder
  sku_completed_qty: number;           // NOTE: different field name from SummaryOrder
  status: ProductionOrderStatus;
  due_date: string | null;
  post_date: string | null;
  warehouse: string;
  priority: number;
  total_components: number;
  components_with_shortfall: number;
  components: BOMComponent[];
}

export interface DetailsMeta {
  total_orders: number;
  total_component_lines: number;
  fetched_at: string;
}

export interface DetailsResponse {
  data: DetailOrder[];
  meta: DetailsMeta;
}

// ─── /procurement/ ───────────────────────────────────────────────────────────

export interface ProcurementItem {
  component_code: string;
  component_name: string;
  uom: string;
  total_required_qty: number;
  stock_on_hand: number;
  stock_committed: number;
  stock_on_order: number;
  net_available: number;
  shortfall_qty: number;               // always >= 0
  suggested_purchase_qty: number;      // = shortfall_qty; add buffer on frontend
  vendor_lead_time: number;
  default_vendor: string;              // may be ""
  related_prod_orders: string[];       // order numbers as strings e.g. ["56", "57"]
}

export interface ProcurementMeta {
  total_components: number;
  components_with_shortfall: number;
  fetched_at: string;
}

export interface ProcurementResponse {
  data: ProcurementItem[];
  meta: ProcurementMeta;
}

// ─── /sku/<doc_entry>/ ───────────────────────────────────────────────────────

export interface SKUDetailData {
  prod_order_entry: number;
  prod_order_num: number;
  sku_code: string;
  sku_name: string;
  sku_planned_qty: number;
  sku_completed_qty: number;
  status: ProductionOrderStatus;
  due_date: string | null;
  post_date: string | null;
  warehouse: string;
  priority: number;
  total_components: number;
  components_with_shortfall: number;
  components: BOMComponent[];
}

export interface SKUDetailResponse {
  data: SKUDetailData;                 // SINGLE OBJECT — not an array
  meta: { fetched_at: string };
}

// ─── Query Filters ────────────────────────────────────────────────────────────

export interface PlanDashboardFilters {
  status?: "planned" | "released" | "all";
  due_date_from?: string;              // "YYYY-MM-DD"
  due_date_to?: string;               // "YYYY-MM-DD"
  warehouse?: string;
  sku?: string;
  show_shortfall_only?: boolean;
}

// ─── API Error ────────────────────────────────────────────────────────────────

export interface APIError {
  detail: string;
  errors?: Record<string, string[]>;   // Only present on 400 responses
}
```

---

## 14. Axios Setup

### 14.1 Axios Instance with Interceptors

```typescript
// lib/api.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 30_000, // 30 seconds — SAP HANA can be slow
});

// ── Request interceptor: attach auth + company headers ──────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("access_token");
  const companyCode = localStorage.getItem("selected_company_code");

  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  if (companyCode) {
    config.headers["Company-Code"] = companyCode;
  }
  return config;
});

// ── Response interceptor: auto-refresh on 401 ──────────────────────────────
let isRefreshing = false;

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Already refreshing — queue this request or reject
        return Promise.reject(error);
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        const res = await axios.post("/api/v1/accounts/token/refresh/", {
          refresh: refreshToken,
        });
        const newAccess = res.data.access;
        const newRefresh = res.data.refresh;

        localStorage.setItem("access_token", newAccess);
        localStorage.setItem("refresh_token", newRefresh);

        originalRequest.headers["Authorization"] = `Bearer ${newAccess}`;
        return api(originalRequest);
      } catch (_) {
        localStorage.clear();
        window.location.href = "/login";
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

### 14.2 Plan Dashboard API Functions

```typescript
// api/sap-plan-dashboard.api.ts
import api from "../lib/api";
import type {
  SummaryResponse,
  DetailsResponse,
  ProcurementResponse,
  SKUDetailResponse,
  PlanDashboardFilters,
} from "../types/sap-plan-dashboard.types";

const BASE = "/api/v1/sap/plan-dashboard";

/**
 * Converts a filter object to URLSearchParams, skipping undefined/empty/null values.
 */
function toParams(filters: PlanDashboardFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  return params;
}

export const planDashboardApi = {
  getSummary: (filters: PlanDashboardFilters = {}): Promise<SummaryResponse> =>
    api.get(`${BASE}/summary/`, { params: toParams(filters) }).then((r) => r.data),

  getDetails: (filters: PlanDashboardFilters = {}): Promise<DetailsResponse> =>
    api.get(`${BASE}/details/`, { params: toParams(filters) }).then((r) => r.data),

  getProcurement: (filters: PlanDashboardFilters = {}): Promise<ProcurementResponse> =>
    api.get(`${BASE}/procurement/`, { params: toParams(filters) }).then((r) => r.data),

  getSKUDetail: (docEntry: number): Promise<SKUDetailResponse> =>
    api.get(`${BASE}/sku/${docEntry}/`).then((r) => r.data),
};
```

---

## 15. React Query Hooks

### 15.1 Query Keys

Use a consistent key structure so `invalidateQueries` works cleanly:

```typescript
// constants/queryKeys.ts
export const planDashboardKeys = {
  all: ["plan-dashboard"] as const,
  summary: (filters: PlanDashboardFilters) =>
    [...planDashboardKeys.all, "summary", filters] as const,
  details: (filters: PlanDashboardFilters) =>
    [...planDashboardKeys.all, "details", filters] as const,
  procurement: (filters: PlanDashboardFilters) =>
    [...planDashboardKeys.all, "procurement", filters] as const,
  skuDetail: (docEntry: number) =>
    [...planDashboardKeys.all, "sku", docEntry] as const,
};
```

### 15.2 Hooks

```typescript
// hooks/usePlanDashboard.ts
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { planDashboardApi } from "../api/sap-plan-dashboard.api";
import { planDashboardKeys } from "../constants/queryKeys";
import type { PlanDashboardFilters } from "../types/sap-plan-dashboard.types";

const STALE_TIME = 5 * 60 * 1000; // 5 minutes

// ── Summary ──────────────────────────────────────────────────────────────────
export const usePlanSummary = (filters: PlanDashboardFilters = {}) =>
  useQuery({
    queryKey: planDashboardKeys.summary(filters),
    queryFn: () => planDashboardApi.getSummary(filters),
    staleTime: STALE_TIME,
    retry: (failureCount, error: any) => {
      // Don't retry on 401, 403, 404 — only on 502, 503
      const status = error?.response?.status;
      if ([401, 403, 404].includes(status)) return false;
      return failureCount < 2;
    },
  });

// ── Details ──────────────────────────────────────────────────────────────────
export const usePlanDetails = (
  filters: PlanDashboardFilters = {},
  enabled = true
) =>
  useQuery({
    queryKey: planDashboardKeys.details(filters),
    queryFn: () => planDashboardApi.getDetails(filters),
    staleTime: STALE_TIME,
    enabled,
  });

// ── Procurement ──────────────────────────────────────────────────────────────
export const usePlanProcurement = (filters: PlanDashboardFilters = {}) =>
  useQuery({
    queryKey: planDashboardKeys.procurement(filters),
    queryFn: () => planDashboardApi.getProcurement(filters),
    staleTime: STALE_TIME,
  });

// ── Single SKU Detail ─────────────────────────────────────────────────────────
export const useSKUDetail = (docEntry: number | null) =>
  useQuery({
    queryKey: planDashboardKeys.skuDetail(docEntry!),
    queryFn: () => planDashboardApi.getSKUDetail(docEntry!),
    staleTime: STALE_TIME,
    enabled: docEntry !== null,   // Only fetches when a row is selected
    retry: (failureCount, error: any) => {
      // Never retry 404 — order not found is a definitive result
      if (error?.response?.status === 404) return false;
      return failureCount < 2;
    },
  });

// ── Manual refresh of all plan-dashboard data ─────────────────────────────────
export const useRefreshPlanDashboard = () => {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: planDashboardKeys.all });
};
```

### 15.3 Usage in a Page Component

```typescript
const PlanDashboardPage: React.FC = () => {
  const [filters, setFilters] = useState<PlanDashboardFilters>({ status: "all" });
  const [activeTab, setActiveTab] = useState<"sku" | "procurement">("sku");
  const [expandedOrderEntry, setExpandedOrderEntry] = useState<number | null>(null);

  const summaryQ = usePlanSummary(filters);
  const procurementQ = usePlanProcurement(filters);
  const skuDetailQ = useSKUDetail(expandedOrderEntry);
  const refresh = useRefreshPlanDashboard();

  // 503 — SAP down
  if (summaryQ.error && (summaryQ.error as any)?.response?.status === 503) {
    return <SAPUnavailableBanner onRetry={refresh} />;
  }

  return (
    <PageLayout>
      <PlanDashboardHeader
        meta={summaryQ.data?.meta}
        onRefresh={refresh}
        refreshing={summaryQ.isFetching}
      />
      <PlanDashboardFilters value={filters} onChange={setFilters} />
      <SummaryStatCards meta={summaryQ.data?.meta} loading={summaryQ.isLoading} />
      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tab value="sku">SKU View</Tab>
        <Tab value="procurement">Procurement</Tab>
      </Tabs>
      {activeTab === "sku" && (
        <SKUSummaryTable
          orders={summaryQ.data?.data ?? []}
          loading={summaryQ.isLoading}
          expandedEntry={expandedOrderEntry}
          onExpandRow={setExpandedOrderEntry}
          detailData={skuDetailQ.data?.data}
          detailLoading={skuDetailQ.isLoading}
        />
      )}
      {activeTab === "procurement" && (
        <ProcurementTable
          items={procurementQ.data?.data ?? []}
          meta={procurementQ.data?.meta}
          loading={procurementQ.isLoading}
        />
      )}
    </PageLayout>
  );
};
```

---

## 16. UI Rules & Display Logic

### 16.1 Stock Status Color Coding

Use `stock_status` to color component rows and badges. Never re-compute this — the backend calculates it correctly.

| `stock_status` | Background | Text | Label | Meaning |
|----------------|-----------|------|-------|---------|
| `"sufficient"` | Green | Dark green | OK | `net_available >= remaining_required` |
| `"partial"` | Amber | Dark amber | Partial | `0 < net_available < remaining_required` |
| `"stockout"` | Red | Dark red | Stockout | `net_available <= 0` |

```typescript
const STOCK_BADGE_STYLES: Record<StockStatus, string> = {
  sufficient: "bg-green-100 text-green-800 border-green-200",
  partial:    "bg-amber-100 text-amber-800 border-amber-200",
  stockout:   "bg-red-100   text-red-800   border-red-200",
};

const STOCK_BADGE_LABELS: Record<StockStatus, string> = {
  sufficient: "OK",
  partial:    "Partial",
  stockout:   "Stockout",
};
```

### 16.2 Production Order Status Badge

| `status` | Color | Label |
|----------|-------|-------|
| `"planned"` | Blue | Planned |
| `"released"` | Green | Released |

### 16.3 Shortfall Highlighting

- `shortfall_qty > 0` → show in **red bold**, add a warning icon
- `shortfall_qty === 0` → show a **green dash** or `—`

```typescript
const ShortfallCell: React.FC<{ qty: number; uom: string }> = ({ qty, uom }) => {
  if (qty === 0) return <span className="text-green-600">—</span>;
  return (
    <span className="text-red-600 font-semibold">
      ⚠ {qty.toFixed(2)} {uom}
    </span>
  );
};
```

### 16.4 Date Formatting

All dates are `"YYYY-MM-DD"` strings or `null`. Format them with your preferred library:

```typescript
import { format, parseISO } from "date-fns";

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return "—";
  return format(parseISO(dateStr), "dd MMM yyyy"); // "20 Mar 2026"
};
```

### 16.5 Number Formatting

SAP quantities can have up to 4 decimal places. Format appropriately:

```typescript
// For KG, LTR — show 2-3 decimal places
const formatQty = (qty: number, uom: string): string => {
  const decimals = ["PC", "BOX", "PKT"].includes(uom) ? 0 : 2;
  return `${qty.toFixed(decimals)} ${uom}`;
};
// e.g. "125.00 KG", "500 PC"
```

### 16.6 Empty Field Handling

| Field | When empty | Display |
|-------|-----------|---------|
| `default_vendor` | `""` | Show `"—"` |
| `component_warehouse` | `""` | Show `"—"` |
| `due_date` | `null` | Show `"—"` |
| `post_date` | `null` | Show `"—"` |
| `vendor_lead_time` | `0` | Show `"—"` or `"Not set"` |

### 16.7 `related_prod_orders` Display

`related_prod_orders` is a `string[]` of production order **numbers** (not DocEntry). Examples: `["56", "57", "60"]`.

```typescript
// Comma-separated
const label = item.related_prod_orders.join(", ");  // "56, 57, 60"

// As clickable tags
item.related_prod_orders.map((num) => (
  <Badge key={num} onClick={() => openOrderDetail(num)}>
    PO-{num}
  </Badge>
));
```

### 16.8 SKU Detail — `data` is an Object, Not Array

The `/sku/<doc_entry>/` endpoint returns a **single object**, not an array. Handle this in TypeScript correctly:

```typescript
// ✅ Correct
const order = skuDetailQ.data?.data;            // SKUDetailData | undefined
const components = order?.components ?? [];     // BOMComponent[]

// ❌ Wrong — data is not an array on this endpoint
const orders = skuDetailQ.data?.data ?? [];     // TypeScript error
```

### 16.9 Suggested Purchase Quantity with Safety Buffer

```typescript
const [bufferPct, setBufferPct] = useState(0); // user-configurable in UI

const getSuggestedQty = (item: ProcurementItem): number => {
  if (item.shortfall_qty === 0) return 0;
  return Math.ceil(item.suggested_purchase_qty * (1 + bufferPct / 100));
};
```

---

## 17. Edge Cases & Gotchas

### 17.1 Field Name Differences Between Endpoints

The summary and details/sku-detail endpoints use slightly different field names for the same logical values:

| Concept | `/summary/` field | `/details/` and `/sku/` field |
|---------|------------------|-----------------------------|
| Planned qty | `planned_qty` | `sku_planned_qty` |
| Completed qty | `completed_qty` | `sku_completed_qty` |
| Status | `status` | `status` ← same ✓ |

### 17.2 `shortfall_qty` is Never Negative

Even if a component has 10× more stock than needed, `shortfall_qty` is always `0`, never negative. Do not show surplus as a negative shortfall.

### 17.3 `stock_on_order` Does Not Reduce Shortfall

`stock_on_order` (items on an open purchase order, not yet received) is included in the response for reference, but the backend does **not** subtract it from the shortfall calculation. The shortfall represents what you need to buy **right now**. Displaying `stock_on_order` helps procurement know that something is already being ordered.

### 17.4 Components Are Items Only

The BOM explosion only includes inventory-tracked component **items**. Resources, sub-contracting services, and non-inventory items are excluded. This is by design — only purchasable physical items appear.

### 17.5 Stale Data

Data is fetched live from SAP HANA on every API call — there is no server-side cache. SAP HANA can sometimes be slow (3–8 seconds). Use React Query's `staleTime: 5 * 60 * 1000` (5 minutes) to avoid repeated calls. Show a "Refresh" button that calls `queryClient.invalidateQueries(planDashboardKeys.all)` to let the user manually refresh.

### 17.6 Multiple Companies

If the user belongs to multiple companies, the `Company-Code` header determines which company's SAP data is shown. Changing the company context (e.g. switching from `JIVO_OIL` to `JIVO_MART`) should:
1. Update the header value
2. Invalidate all plan-dashboard queries: `queryClient.invalidateQueries(planDashboardKeys.all)`

### 17.7 `prod_order_entry` vs `prod_order_num`

| Field | Use For |
|-------|---------|
| `prod_order_entry` | API calls — `/sku/<doc_entry>/` URL parameter |
| `prod_order_num` | Display only — show to users as "PO-56" |

Never display `prod_order_entry` to users. Never use `prod_order_num` in API calls.

### 17.8 Empty `default_vendor`

Many items don't have a default vendor configured in SAP. When `default_vendor` is `""`, show a dash `"—"`. Do not make a vendor API call to resolve it — there's no vendor lookup endpoint in this module.

### 17.9 Large Result Sets

`/details/` can return hundreds of component lines. If performance is a concern:
- Use `/summary/` for the table and `/sku/<doc_entry>/` on expand (lazy loading)
- Add `show_shortfall_only=true` to reduce result size
- Implement virtual scrolling for tables with > 100 rows

### 17.10 `priority` Field

SAP's `priority` is an integer. There is no enum mapping defined — display as-is (e.g. "Priority 2") or use your app's own priority label system. `0` means no specific priority.

---

## 18. Permissions

### 18.1 Required Permission

The user must have the `can_view_plan_dashboard` permission in their Django profile. Without it, all four endpoints return `403 Forbidden`.

```
HTTP/1.1 403 Forbidden
{
  "detail": "You do not have permission to perform this action."
}
```

### 18.2 How to Check Permissions on the Frontend

After login, call `GET /api/v1/accounts/me/` to get the user's permission list:

```
GET /api/v1/accounts/me/
Authorization: Bearer <token>
```

Look for `"sap_plan_dashboard.can_view_plan_dashboard"` in the permissions array. If it's not there, hide the dashboard navigation link and show a "Contact admin" message if the user tries to access it directly.

### 18.3 Checking in React

```typescript
const canViewDashboard = user?.permissions?.includes(
  "sap_plan_dashboard.can_view_plan_dashboard"
);

// In routing:
<Route
  path="/plan-dashboard"
  element={canViewDashboard ? <PlanDashboardPage /> : <AccessDenied />}
/>
```

### 18.4 Available Permissions

| Permission codename | Description |
|---------------------|-------------|
| `can_view_plan_dashboard` | Access all four plan dashboard endpoints |
| `can_export_plan_dashboard` | Reserved for a future export endpoint (not yet active) |

---

## 19. Change Log

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-03-13 | Initial release — 4 endpoints: summary, details, procurement, sku-detail |

---

*Document maintained by the backend team. For questions or discrepancies, open a ticket or ping the backend channel.*
