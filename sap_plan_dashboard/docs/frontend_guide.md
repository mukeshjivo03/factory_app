# SAP Plan Dashboard — Frontend Developer Guide

Everything a frontend developer needs to integrate with the Plan Dashboard API.

---

## Table of Contents

1. [Authentication Setup](#1-authentication-setup)
2. [Required Headers](#2-required-headers)
3. [Base URL & Endpoints Overview](#3-base-url--endpoints-overview)
4. [Endpoint Details](#4-endpoint-details)
   - [GET /summary/](#41-get-summary)
   - [GET /details/](#42-get-details)
   - [GET /procurement/](#43-get-procurement)
   - [GET /sku/\<doc_entry\>/](#44-get-skudoc_entry)
5. [Query Parameters Reference](#5-query-parameters-reference)
6. [Error Handling Guide](#6-error-handling-guide)
7. [TypeScript Types](#7-typescript-types)
8. [React Query Hooks Example](#8-react-query-hooks-example)
9. [UI Logic Guide](#9-ui-logic-guide)
10. [Frequently Asked Questions](#10-frequently-asked-questions)

---

## 1. Authentication Setup

This API uses **JWT Bearer token** authentication. Obtain tokens from the login endpoint.

### Login

```
POST /api/v1/accounts/login/
Content-Type: application/json

{
  "email": "user@company.com",
  "password": "password"
}
```

**Response:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": { "id": 1, "email": "user@company.com", "full_name": "John Doe" },
  "companies": [
    { "code": "JIVO_OIL", "name": "Jivo Oil", "role": "Planner", "is_default": true }
  ]
}
```

Store `access` and `refresh` tokens securely (memory or httpOnly cookie). The `access` token is valid for 25 hours; refresh with `/api/v1/accounts/token/refresh/` before expiry.

---

## 2. Required Headers

Every request to the plan dashboard **must** include both headers:

```
Authorization: Bearer <access_token>
Company-Code: JIVO_OIL
```

Set the `Company-Code` from the selected company in your app context. If either header is missing, you will receive a `401` or `403` response.

---

## 3. Base URL & Endpoints Overview

**Base path:** `/api/v1/sap/plan-dashboard/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/summary/` | One row per production order — shortfall counts |
| GET | `/details/` | Full BOM explosion — all component lines per order |
| GET | `/procurement/` | Aggregated purchase requirements per component |
| GET | `/sku/<doc_entry>/` | Single production order full detail |

All endpoints are **read-only** (GET only). No POST/PUT/DELETE.

---

## 4. Endpoint Details

---

### 4.1 GET `/summary/`

**Purpose:** Power the main SKU summary table. One row per production order.

**When to call:** On page load and on filter changes.

#### Request

```
GET /api/v1/sap/plan-dashboard/summary/
    ?status=planned
    &due_date_from=2026-03-01
    &due_date_to=2026-03-31

Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Response Body — `200 OK`

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

#### Key Fields to Display

| Field | Where to Show |
|-------|--------------|
| `prod_order_num` | Order number column (e.g. "PO-56") |
| `sku_code` + `sku_name` | SKU column |
| `planned_qty` | Qty column |
| `due_date` | Due date column |
| `status` | Status badge (planned=blue, released=green) |
| `total_components` + `components_with_shortfall` | "8 (3 short)" format |
| `meta.total_orders` | Summary card: "Total Orders" |
| `meta.orders_with_shortfall` | Summary card: "Orders at Risk" |

---

### 4.2 GET `/details/`

**Purpose:** Power the expandable BOM rows in the SKU view. Returns all orders with nested component lines.

**When to call:** When user switches to the "BOM Detail" view or expands all rows. This is a heavier call — consider lazy-loading per order using `/sku/<doc_entry>/` instead.

#### Request

```
GET /api/v1/sap/plan-dashboard/details/
    ?show_shortfall_only=true

Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Response Body — `200 OK`

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

---

### 4.3 GET `/procurement/`

**Purpose:** Power the "Procurement View" tab. One row per component aggregated across all open orders.

**When to call:** When user switches to the "Procurement" tab.

#### Request

```
GET /api/v1/sap/plan-dashboard/procurement/
    ?show_shortfall_only=true

Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Response Body — `200 OK`

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

> **Rows are pre-sorted** by `shortfall_qty` descending (worst shortfalls first). You don't need to sort on the frontend by default, but you can re-sort by other columns.

> **Safety buffer:** `suggested_purchase_qty` equals `shortfall_qty` from the server. If your business needs a safety buffer (e.g. 10%), calculate it on the frontend: `suggestedQty * 1.1`.

---

### 4.4 GET `/sku/<doc_entry>/`

**Purpose:** Load the full detail of one production order when user clicks a row or expands it.

**When to call:** On row expand or detail panel open. Use `prod_order_entry` from the summary response as the `<doc_entry>` path param.

#### Request

```
GET /api/v1/sap/plan-dashboard/sku/1234/

Authorization: Bearer <token>
Company-Code: JIVO_OIL
```

#### Response Body — `200 OK`

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
      }
    ]
  },
  "meta": {
    "fetched_at": "2026-03-13T10:30:00+00:00"
  }
}
```

**Note:** `data` is a single object here (not an array), unlike the other endpoints which return `data` as an array.

#### Error — `404 Not Found`

```json
{
  "detail": "Production order 9999 not found or is not in Planned/Released status."
}
```

This happens when:
- The `doc_entry` doesn't exist in SAP.
- The production order is Closed or Cancelled (not shown in dashboard).

---

## 5. Query Parameters Reference

| Parameter | Type | Default | Accepted Values |
|-----------|------|---------|-----------------|
| `status` | string | `all` | `planned`, `released`, `all` |
| `due_date_from` | string | — | `YYYY-MM-DD` |
| `due_date_to` | string | — | `YYYY-MM-DD` |
| `warehouse` | string | — | Any warehouse code (e.g. `WH-01`) |
| `sku` | string | — | Any item code (e.g. `FG-001`) |
| `show_shortfall_only` | boolean | `false` | `true`, `false` |

### Sending Boolean Values

Pass booleans as strings in query params:
```
?show_shortfall_only=true    ✅ correct
?show_shortfall_only=1       ✅ also works
?show_shortfall_only=True    ❌ case-sensitive, use lowercase
```

---

## 6. Error Handling Guide

### Error Response Shape

All errors follow this pattern:

```json
{
  "detail": "Human-readable description of the error"
}
```

Filter validation errors also include an `errors` object:

```json
{
  "detail": "Invalid query parameters.",
  "errors": {
    "status": ["\"completed\" is not a valid choice."],
    "due_date_from": ["Date has wrong format. Use one of these formats instead: YYYY-MM-DD."]
  }
}
```

### HTTP Status Code Reference

| Status | When | What to Show |
|--------|------|--------------|
| `200 OK` | Success | Render data |
| `400 Bad Request` | Invalid query params | Show validation errors inline on filters |
| `401 Unauthorized` | Token missing / expired | Redirect to login |
| `403 Forbidden` | Wrong company or no permission | Show "Access denied" message |
| `404 Not Found` | SKU detail — order not found | Show "Order not found" in the detail panel |
| `502 Bad Gateway` | SAP HANA query failed | Show "Data error from SAP" banner |
| `503 Service Unavailable` | SAP HANA unreachable | Show "SAP system unavailable" banner with retry button |

### Recommended Error UI Pattern

```typescript
// Pseudo-code
if (error.status === 401) {
  redirectToLogin();
} else if (error.status === 403) {
  showToast("You don't have permission to view the plan dashboard.");
} else if (error.status === 503) {
  showBanner("SAP system is currently unavailable. Please try again later.", {
    action: "Retry",
    onAction: refetch,
  });
} else if (error.status === 502) {
  showBanner("Failed to load data from SAP. Contact your system administrator.");
} else if (error.status === 404) {
  showInPanel("Production order not found.");
}
```

---

## 7. TypeScript Types

```typescript
// types/sap-plan-dashboard.types.ts

export type ProductionOrderStatus = "planned" | "released";
export type StockStatus = "sufficient" | "partial" | "stockout";

// ── Summary ──────────────────────────────────────────────────

export interface SummaryOrder {
  prod_order_entry: number;
  prod_order_num: number;
  sku_code: string;
  sku_name: string;
  planned_qty: number;
  completed_qty: number;
  status: ProductionOrderStatus;
  due_date: string | null;        // "YYYY-MM-DD"
  post_date: string | null;       // "YYYY-MM-DD"
  priority: number;
  warehouse: string;
  total_components: number;
  components_with_shortfall: number;
  total_remaining_component_qty: number;
}

export interface SummaryMeta {
  total_orders: number;
  orders_with_shortfall: number;
  fetched_at: string;             // ISO 8601
}

export interface SummaryResponse {
  data: SummaryOrder[];
  meta: SummaryMeta;
}

// ── BOM Component (shared between details & sku-detail) ──────

export interface BOMComponent {
  component_line: number;
  component_code: string;
  component_name: string;
  component_planned_qty: number;
  component_issued_qty: number;
  component_remaining_qty: number;
  component_warehouse: string;
  base_qty: number;
  uom: string;
  stock_on_hand: number;
  stock_committed: number;
  stock_on_order: number;
  net_available: number;
  shortfall_qty: number;
  vendor_lead_time: number;
  default_vendor: string;
  stock_status: StockStatus;
}

// ── Details ──────────────────────────────────────────────────

export interface DetailOrder {
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

export interface DetailsMeta {
  total_orders: number;
  total_component_lines: number;
  fetched_at: string;
}

export interface DetailsResponse {
  data: DetailOrder[];
  meta: DetailsMeta;
}

// ── Procurement ──────────────────────────────────────────────

export interface ProcurementItem {
  component_code: string;
  component_name: string;
  uom: string;
  total_required_qty: number;
  stock_on_hand: number;
  stock_committed: number;
  stock_on_order: number;
  net_available: number;
  shortfall_qty: number;
  suggested_purchase_qty: number;
  vendor_lead_time: number;
  default_vendor: string;
  related_prod_orders: string[];
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

// ── SKU Detail ───────────────────────────────────────────────

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
  data: SKUDetailData;    // NOTE: single object, not an array
  meta: { fetched_at: string };
}

// ── Filters ──────────────────────────────────────────────────

export interface PlanDashboardFilters {
  status?: "planned" | "released" | "all";
  due_date_from?: string;   // "YYYY-MM-DD"
  due_date_to?: string;     // "YYYY-MM-DD"
  warehouse?: string;
  sku?: string;
  show_shortfall_only?: boolean;
}

// ── Error ─────────────────────────────────────────────────────

export interface APIError {
  detail: string;
  errors?: Record<string, string[]>;
}
```

---

## 8. React Query Hooks Example

```typescript
// api/sap-plan-dashboard.api.ts

import axios from "axios";
import type {
  SummaryResponse, DetailsResponse, ProcurementResponse,
  SKUDetailResponse, PlanDashboardFilters
} from "../types/sap-plan-dashboard.types";

const BASE = "/api/v1/sap/plan-dashboard";

// Convert filters object to URLSearchParams, skipping undefined/empty
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
    axios.get(`${BASE}/summary/`, { params: toParams(filters) }).then(r => r.data),

  getDetails: (filters: PlanDashboardFilters = {}): Promise<DetailsResponse> =>
    axios.get(`${BASE}/details/`, { params: toParams(filters) }).then(r => r.data),

  getProcurement: (filters: PlanDashboardFilters = {}): Promise<ProcurementResponse> =>
    axios.get(`${BASE}/procurement/`, { params: toParams(filters) }).then(r => r.data),

  getSKUDetail: (docEntry: number): Promise<SKUDetailResponse> =>
    axios.get(`${BASE}/sku/${docEntry}/`).then(r => r.data),
};
```

```typescript
// api/sap-plan-dashboard.queries.ts

import { useQuery } from "@tanstack/react-query";
import { planDashboardApi } from "./sap-plan-dashboard.api";
import type { PlanDashboardFilters } from "../types/sap-plan-dashboard.types";

const STALE_TIME = 5 * 60 * 1000; // 5 minutes — SAP data doesn't change in real-time

export const usePlanSummary = (filters: PlanDashboardFilters = {}) =>
  useQuery({
    queryKey: ["plan-dashboard", "summary", filters],
    queryFn: () => planDashboardApi.getSummary(filters),
    staleTime: STALE_TIME,
  });

export const usePlanDetails = (filters: PlanDashboardFilters = {}, enabled = true) =>
  useQuery({
    queryKey: ["plan-dashboard", "details", filters],
    queryFn: () => planDashboardApi.getDetails(filters),
    staleTime: STALE_TIME,
    enabled,
  });

export const usePlanProcurement = (filters: PlanDashboardFilters = {}) =>
  useQuery({
    queryKey: ["plan-dashboard", "procurement", filters],
    queryFn: () => planDashboardApi.getProcurement(filters),
    staleTime: STALE_TIME,
  });

export const useSKUDetail = (docEntry: number | null) =>
  useQuery({
    queryKey: ["plan-dashboard", "sku", docEntry],
    queryFn: () => planDashboardApi.getSKUDetail(docEntry!),
    staleTime: STALE_TIME,
    enabled: docEntry !== null,  // Only fetch when a row is selected
  });
```

### Usage in a Component

```typescript
const PlanDashboardPage = () => {
  const [filters, setFilters] = useState<PlanDashboardFilters>({ status: "all" });
  const [activeTab, setActiveTab] = useState<"sku" | "procurement">("sku");
  const [selectedOrderEntry, setSelectedOrderEntry] = useState<number | null>(null);

  const summaryQuery = usePlanSummary(filters);
  const procurementQuery = usePlanProcurement(filters);
  const skuDetailQuery = useSKUDetail(selectedOrderEntry);

  if (summaryQuery.isError) {
    const err = summaryQuery.error as any;
    if (err?.response?.status === 503) {
      return <SAPUnavailableBanner onRetry={summaryQuery.refetch} />;
    }
    // handle other errors...
  }

  return (
    <div>
      <PlanDashboardFilters value={filters} onChange={setFilters} />
      <SummaryCards meta={summaryQuery.data?.meta} />
      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tab value="sku">SKU View</Tab>
        <Tab value="procurement">Procurement</Tab>
      </Tabs>
      {activeTab === "sku" && (
        <SKUSummaryTable
          orders={summaryQuery.data?.data ?? []}
          loading={summaryQuery.isLoading}
          onRowExpand={setSelectedOrderEntry}
          expandedOrderDetail={skuDetailQuery.data?.data}
          expandedLoading={skuDetailQuery.isLoading}
        />
      )}
      {activeTab === "procurement" && (
        <ProcurementTable
          items={procurementQuery.data?.data ?? []}
          loading={procurementQuery.isLoading}
        />
      )}
    </div>
  );
};
```

---

## 9. UI Logic Guide

### Stock Status Color Coding

Use `stock_status` from each component to color-code rows:

| `stock_status` | Color | Meaning |
|----------------|-------|---------|
| `sufficient` | Green | `net_available >= component_remaining_qty` — no action needed |
| `partial` | Amber/Orange | `0 < net_available < required` — partial shortage |
| `stockout` | Red | `net_available <= 0` — no stock at all |

```typescript
const STOCK_STATUS_COLORS = {
  sufficient: "text-green-600 bg-green-50",
  partial:    "text-amber-600 bg-amber-50",
  stockout:   "text-red-600 bg-red-50",
};

const STOCK_STATUS_LABELS = {
  sufficient: "OK",
  partial:    "Partial",
  stockout:   "Stockout",
};
```

### Production Order Status Badge

| `status` value | Badge Color | Label |
|----------------|-------------|-------|
| `planned` | Blue | Planned |
| `released` | Green | Released |

### Shortfall Highlighting

When `shortfall_qty > 0`, highlight the cell in red. When `shortfall_qty === 0`, show a dash or green zero.

### Related Production Orders (Procurement View)

`related_prod_orders` is an array of strings: `["56", "57", "60"]`. Display as a comma-separated list or as tags. These are production order numbers (user-visible), not internal DocEntry IDs.

### Suggested Purchase Quantity with Buffer

The API returns `suggested_purchase_qty === shortfall_qty`. If your app has a configurable safety buffer:

```typescript
const withBuffer = (qty: number, bufferPct = 0) =>
  Math.ceil(qty * (1 + bufferPct / 100));

// e.g. 10% buffer:
const suggestedWithBuffer = withBuffer(item.suggested_purchase_qty, 10);
```

### Date Formatting

All dates are returned as `"YYYY-MM-DD"` strings or `null`. Format them using your preferred date library:

```typescript
import { format, parseISO } from "date-fns";

const formatDate = (dateStr: string | null) =>
  dateStr ? format(parseISO(dateStr), "dd MMM yyyy") : "—";

// "2026-03-20" → "20 Mar 2026"
```

### Loading States

- Show a **skeleton table** while `isLoading === true`.
- Show the previous data with an **overlay spinner** while `isFetching === true` (refetch in background).
- On the SKU detail panel, show a spinner while `skuDetailQuery.isLoading`.

---

## 10. Frequently Asked Questions

**Q: Why does `data` in `/sku/<doc_entry>/` return an object, not an array?**

A: The SKU detail endpoint is for a single production order, so `data` is one object. All other endpoints return `data` as an array. TypeScript types reflect this difference (`SKUDetailResponse.data` vs `SummaryResponse.data`).

---

**Q: Why is `shortfall_qty` sometimes 0 even when `net_available < stock_on_hand`?**

A: `shortfall_qty = max(0, component_remaining_qty - net_available)`. If the component has already been fully issued (`component_remaining_qty === 0`), there is no shortfall regardless of stock levels. This is intentional — we only care about what still needs to be produced.

---

**Q: Can I filter by multiple warehouses?**

A: No, the `warehouse` parameter accepts a single warehouse code. To see all warehouses, omit the parameter.

---

**Q: Why do I sometimes get `default_vendor: ""`?**

A: Some items in SAP don't have a default vendor configured. Show a dash `"—"` when the field is empty.

---

**Q: What is `prod_order_entry` vs `prod_order_num`?**

A: `prod_order_entry` is SAP's internal `DocEntry` (used in the `/sku/<doc_entry>/` URL). `prod_order_num` is the user-visible document number shown in SAP B1 (prefix with "PO-" or show as-is). Always use `prod_order_entry` as the key for API calls, and `prod_order_num` for display.

---

**Q: How often does the data refresh?**

A: Data is fetched live from SAP HANA on every API request — there is no server-side cache. Use React Query's `staleTime: 5 * 60 * 1000` (5 minutes) to avoid hammering the SAP server. Add a manual "Refresh" button that calls `queryClient.invalidateQueries(["plan-dashboard"])`.

---

**Q: How do I implement a CSV/Excel export?**

A: Call `/procurement/` with your current filters, then use a library like `xlsx` or `papaparse` to convert `data` to CSV/Excel on the frontend. No dedicated export endpoint exists yet (it's planned as a future backend feature).

---

**Q: The API returns `503` frequently. What's wrong?**

A: `503` means the backend could not connect to SAP HANA. This is a network or SAP server issue. Show a retry button and contact the system administrator. Do not retry automatically in a tight loop — use exponential backoff.

---

**Q: How do I know if a production order has any issue?**

A: Check `components_with_shortfall > 0` on summary/detail responses. If non-zero, at least one BOM component doesn't have enough stock. You can also check `components_with_shortfall === total_components` for fully at-risk orders.

---

**Q: What does `show_shortfall_only=true` do on `/details/`?**

A: It removes all component lines where `shortfall_qty === 0`. If a production order has ALL components in stock, the entire order is removed from the response. If it has at least one shortfall component, the order appears but only its shortfall components are included.

---

*Last updated: 2026-03-13 | Backend: sap_plan_dashboard Django app*
