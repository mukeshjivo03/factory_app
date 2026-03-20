# SAP Plan — Application Flow Documentation

## Overview

The SAP Plan feature consists of **two Django apps** working together:

| App | Purpose |
|-----|---------|
| **sap_plan_dashboard** | Read-only dashboard that queries SAP HANA live to show production order status, BOM shortfalls, and procurement needs |
| **production_execution** | Transactional app where factory floor staff record production runs, breakdowns, QC checks, waste, resources, and costs — all linked back to SAP production orders via `sap_doc_entry` |

---

## High-Level Architecture

```
┌──────────────┐         ┌───────────────────────┐         ┌──────────────┐
│   SAP HANA   │◄────────│  sap_plan_dashboard   │────────►│   Frontend   │
│  (Read-Only) │  SQL    │  (Live HANA Queries)  │  REST   │  (Dashboard) │
└──────────────┘         └───────────────────────┘         └──────────────┘

┌──────────────┐         ┌───────────────────────┐         ┌──────────────┐
│   SAP HANA   │◄────────│ production_execution  │────────►│   Frontend   │
│  + SAP B1    │  SQL/   │  (Django Models + DB) │  REST   │  (Execution) │
│  Service Lyr │  HTTP   └───────────────────────┘         └──────────────┘
└──────────────┘
```

---

## 1. SAP Plan Dashboard Flow

### Purpose
Gives planners and managers a **real-time view** of open SAP production orders, their BOM component availability, and what needs to be procured.

### Data Source
All data comes from **live SAP HANA SQL queries** — no local database tables are used (except a sentinel permission model).

### SAP Tables Queried
- **OWOR** — Production Orders (header: DocEntry, DocNum, ItemCode, PlannedQty, Status, etc.)
- **WOR1** — Production Order BOM Lines (components, planned qty, issued qty)
- **OITM** — Item Master (stock on hand, committed stock, ordered stock)
- **OCRD** — Business Partners (default vendor info)

### API Endpoints & Flow

#### 1.1 Summary View — `GET /api/v1/sap/plan-dashboard/summary/`

```
User Request (with filters)
    │
    ▼
PlanDashboardSummaryAPI (View)
    │
    ├── Validates filters (PlanDashboardFilterSerializer)
    │   Filters: status, due_date_from, due_date_to, warehouse, sku, show_shortfall_only
    │
    ▼
PlanDashboardService.get_summary(filters)
    │
    ▼
HanaPlanDashboardReader.get_summary(filters)
    │
    ├── Builds SQL query against OWOR + WOR1 + OITM
    │   WHERE: Status IN ('P','R'), ItemType=4, InvntItem='Y'
    │   GROUP BY: Production Order
    │
    ├── Executes on HANA via hdbcli
    │
    ▼
Returns: One row per production order with:
    - SKU code, name, planned/completed qty
    - Component shortfall count (aggregated)
    - Due date, warehouse, status
    + Meta: total_orders, orders_with_shortfall, fetched_at
```

**Use case**: Quick overview — "Which orders have material shortages?"

#### 1.2 Details View — `GET /api/v1/sap/plan-dashboard/details/`

```
Same filter flow as Summary
    │
    ▼
HanaPlanDashboardReader.get_details(filters)
    │
    ├── Full BOM explosion query
    │   Returns one row per component line per order
    │
    ▼
PlanDashboardService.get_details(filters)
    │
    ├── Groups flat rows by order (_group_details_by_order)
    │   Each order → { header, components[] }
    │
    ├── Optionally filters to only show orders with shortfall
    │
    ▼
Returns: Nested structure
    - Order header + components[], each with:
      - component_code, planned/issued/remaining qty
      - stock_on_hand, stock_committed, stock_on_order
      - net_available, shortfall_qty
      - stock_status: 'sufficient' | 'partial' | 'stockout'
      - vendor_lead_time, default_vendor
```

**Use case**: "What exactly is short for each order?"

#### 1.3 Procurement View — `GET /api/v1/sap/plan-dashboard/procurement/`

```
Same filter flow
    │
    ▼
HanaPlanDashboardReader.get_details(filters)   ← reuses details query
    │
    ▼
PlanDashboardService.get_procurement(filters)
    │
    ├── _aggregate_procurement():
    │   Groups by component_code across ALL orders
    │   Sums total_required_qty
    │   Calculates shortfall = required - net_available
    │   Suggests purchase qty
    │   Lists related_prod_orders[]
    │
    ├── Sorts by shortfall_qty DESC (most critical first)
    │
    ▼
Returns: One row per unique component
    - total_required_qty (across all orders)
    - stock levels, shortfall, suggested_purchase_qty
    - related_prod_orders[] (which orders need this component)
```

**Use case**: "What do I need to buy, and how much?"

#### 1.4 SKU Detail View — `GET /api/v1/sap/plan-dashboard/sku/<doc_entry>/`

```
Path param: doc_entry (SAP OWOR DocEntry)
    │
    ▼
HanaPlanDashboardReader.get_sku_detail(doc_entry)
    │
    ├── Same BOM query filtered to single order
    │
    ▼
Returns: Full order header + all BOM component lines with stock data
```

**Use case**: "Deep dive into one specific production order"

---

## 2. Production Execution Flow

### Purpose
Factory floor staff use this app to **record everything that happens** during a production run — linking each run back to SAP via `sap_doc_entry`.

### Data Source
All transactional data is stored in **local Django/PostgreSQL models**. SAP is read for order selection and written to for goods receipts.

### Core Flow (Life of a Production Run)

```
┌─────────────────────────────────────────────────────────┐
│  STEP 1: SELECT SAP ORDER                               │
│                                                         │
│  GET /sap/orders/                                       │
│  → Fetches released SAP orders (Status='R')             │
│  → Shows: DocEntry, ItemCode, PlannedQty, RemainingQty  │
│                                                         │
│  GET /sap/orders/<doc_entry>/                            │
│  → Full order detail + BOM components                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: LINE CLEARANCE (Pre-Production)                │
│                                                         │
│  POST /line-clearance/                                  │
│  → Create clearance with sap_doc_entry + line + date    │
│  → 9 standard checklist items auto-created              │
│  → Status: DRAFT                                        │
│                                                         │
│  POST /line-clearance/<id>/submit/  → Status: SUBMITTED │
│  POST /line-clearance/<id>/approve/ → Status: CLEARED   │
│  (QA must approve before production can start)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: CREATE PRODUCTION RUN                          │
│                                                         │
│  POST /runs/                                            │
│  Body: sap_doc_entry, date, line, run_number,           │
│        brand, pack, sap_order_no, rated_speed           │
│  → Status: DRAFT                                        │
│  → Linked to SAP order via sap_doc_entry                │
│  → Unique: (company, sap_doc_entry, date, run_number)   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 4: RECORD PRODUCTION DATA (During Run)            │
│                                                         │
│  ┌─────────────────────────────────────────┐            │
│  │ Hourly Production Logs                  │            │
│  │ POST /runs/<id>/logs/                   │            │
│  │ → 12 time slots (07:00-19:00)           │            │
│  │ → Cases produced, machine status        │            │
│  └─────────────────────────────────────────┘            │
│                                                         │
│  ┌─────────────────────────────────────────┐            │
│  │ Machine Breakdowns                      │            │
│  │ POST /runs/<id>/breakdowns/             │            │
│  │ → Machine, start/end time, minutes      │            │
│  │ → Type: LINE or EXTERNAL                │            │
│  │ → Reason, remarks                       │            │
│  └─────────────────────────────────────────┘            │
│                                                         │
│  ┌─────────────────────────────────────────┐            │
│  │ Material Usage                          │            │
│  │ POST /runs/<id>/materials/              │            │
│  │ → Opening, issued, closing, wastage qty │            │
│  │ → Batch tracking                        │            │
│  └─────────────────────────────────────────┘            │
│                                                         │
│  ┌─────────────────────────────────────────┐            │
│  │ Machine Runtime                         │            │
│  │ POST /runs/<id>/machine-runtime/        │            │
│  │ → Runtime & downtime per machine type   │            │
│  └─────────────────────────────────────────┘            │
│                                                         │
│  ┌─────────────────────────────────────────┐            │
│  │ Manpower                                │            │
│  │ POST /runs/<id>/manpower/               │            │
│  │ → Workers per shift, supervisor, engg   │            │
│  └─────────────────────────────────────────┘            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 5: QUALITY CHECKS                                 │
│                                                         │
│  In-Process QC:                                         │
│  POST /runs/<id>/qc/inprocess/                          │
│  → Parameter, min/max acceptable, actual value          │
│  → Result: PASS / FAIL / NA                             │
│                                                         │
│  Final QC:                                              │
│  POST /runs/<id>/qc/final/                              │
│  → Overall result: PASS / FAIL / CONDITIONAL            │
│  → Parameters stored as JSON array                      │
│  → {name, expected, actual, result} per check           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 6: RESOURCE TRACKING                              │
│                                                         │
│  POST /runs/<id>/resources/electricity/                  │
│  POST /runs/<id>/resources/water/                        │
│  POST /runs/<id>/resources/gas/                          │
│  POST /runs/<id>/resources/compressed-air/               │
│  POST /runs/<id>/resources/labour/                       │
│  POST /runs/<id>/resources/machine-costs/                │
│  POST /runs/<id>/resources/overhead/                     │
│                                                         │
│  Each tracks: qty/units consumed × rate = total_cost    │
│  (auto-calculated)                                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 7: WASTE MANAGEMENT (Multi-Level Approval)        │
│                                                         │
│  POST /waste/                                           │
│  → material, wastage_qty, reason                        │
│  → Status: PENDING                                      │
│                                                         │
│  Sequential Approval Chain:                             │
│  1. POST /waste/<id>/approve/engineer/  → Engineer sign │
│  2. POST /waste/<id>/approve/am/        → AM sign       │
│  3. POST /waste/<id>/approve/store/     → Store sign    │
│  4. POST /waste/<id>/approve/hod/       → HOD sign      │
│                                                         │
│  → Status moves: PENDING → PARTIALLY → FULLY_APPROVED   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 8: COMPLETE RUN                                   │
│                                                         │
│  POST /runs/<id>/complete/                              │
│  → Status: DRAFT → COMPLETED                            │
│  → Aggregates: total_production, total_minutes,         │
│    breakdown times, unrecorded time                     │
│                                                         │
│  Cost Calculation (auto):                               │
│  GET /runs/<id>/cost/                                   │
│  → Sums all resource costs                              │
│  → Calculates per_unit_cost = total / produced_qty      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 9: SAP GOODS RECEIPT (Post-Production)            │
│                                                         │
│  GoodsReceiptWriter.post_goods_receipt()                │
│  → POST to SAP B1 Service Layer:                        │
│    /b1s/v2/InventoryGenEntries                          │
│  → Links back via BaseType=202, BaseEntry=doc_entry     │
│  → Updates SAP completed qty                            │
└─────────────────────────────────────────────────────────┘
```

### Machine Checklists (Maintenance — Parallel Flow)

```
POST /machine-checklists/          → Individual entry
POST /machine-checklists/bulk/     → Bulk creation

Fields: machine, date, task, frequency (DAILY/WEEKLY/MONTHLY),
        status (OK/NOT_OK/NA), operator, shift_incharge
Unique: (machine, template, date)
```

---

## 3. Reporting & Analytics

| Endpoint | What It Shows |
|----------|---------------|
| `GET /reports/daily/` | Daily production summary across all runs |
| `GET /reports/yield/` | Material yield / efficiency |
| `GET /reports/line-clearance/` | Clearance compliance metrics |
| `GET /reports/analytics/` | General production analytics |
| `GET /reports/analytics/oee/` | **OEE** — Availability × Performance × Quality |
| `GET /reports/analytics/downtime/` | Downtime breakdown (by machine, type, reason) |
| `GET /reports/analytics/waste/` | Waste analysis (by material, reason, trend) |
| `GET /costs/analytics/` | Cost trends and per-unit cost analysis |

---

## 4. Authentication & Multi-Tenancy

- **Auth**: JWT Bearer tokens (SimpleJWT)
- **Multi-Tenant**: Every request requires a `Company-Code` header. All queries are scoped to the authenticated user's company.
- **Permissions**: 30+ granular permissions on ProductionRun model alone. Each API endpoint enforces specific permission classes.

---

## 5. SAP Integration Summary

| Direction | Method | What | Where |
|-----------|--------|------|-------|
| **Read** | HANA SQL (hdbcli) | Production orders, BOM, stock levels | `hana_reader.py`, `sap_reader.py` |
| **Write** | SAP B1 Service Layer (HTTP) | Goods receipts | `sap_writer.py` |

**Key Link Field**: `sap_doc_entry` (integer) — maps to SAP `OWOR.DocEntry`
- Used in: `ProductionRun`, `LineClearance`
- Replaced the old local `ProductionPlan` FK (removed in migration 0004)

---

## 6. Data Model Relationships

```
ProductionRun (core entity)
    │
    ├── ProductionLog[]          (hourly slots)
    ├── MachineBreakdown[]       (downtime events)
    ├── ProductionMaterialUsage[] (raw materials)
    ├── MachineRuntime[]         (per-machine runtime)
    ├── ProductionManpower[]     (per-shift staffing)
    ├── WasteLog[]               (waste + 4-level approval)
    ├── InProcessQCCheck[]       (in-line QC)
    ├── FinalQCCheck             (1:1, end-of-run QC)
    ├── ProductionRunCost        (1:1, calculated costs)
    │
    ├── ResourceElectricity[]
    ├── ResourceWater[]
    ├── ResourceGas[]
    ├── ResourceCompressedAir[]
    ├── ResourceLabour[]
    ├── ResourceMachineCost[]
    └── ResourceOverhead[]

ProductionLine
    ├── Machine[]
    └── LineClearance[]

MachineChecklistTemplate
    └── MachineChecklistEntry[]
```
