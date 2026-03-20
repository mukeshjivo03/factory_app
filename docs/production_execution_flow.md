# Production Execution App — Detailed Flow Documentation

## Overview

The `production_execution` app is a comprehensive Django-based production management system for factory operations. It records everything that happens on the factory floor — production runs, hourly output, machine breakdowns, material usage, quality checks, waste management, resource costs, and analytics — all linked to SAP production orders.

**Base URL**: `/api/v1/production-execution/`

**Authentication**: JWT Bearer token + `Company-Code` header (multi-tenant)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          VIEWS (views.py)                        │
│  40+ APIView classes — validates input, delegates to service     │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                  SERVICES (services/ directory)                   │
│                                                                  │
│  ProductionExecutionService  — Core business logic (957 lines)   │
│  ProductionOrderReader       — SAP HANA queries (100 lines)      │
│  GoodsReceiptWriter          — SAP B1 Service Layer (87 lines)   │
│  recalculate_run_cost()      — Cost aggregation (85 lines)       │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                     MODELS (models.py)                            │
│  23 models, 12 choice enums, 854 lines                          │
│  All company-scoped with ForeignKey to Company                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Master Data Setup

Before any production can begin, these master records must be configured.

### 1.1 Production Lines

A production line represents a physical manufacturing line in the factory.

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/lines/` | GET | `can_view_production_run` | List lines (filter: `?is_active=true`) |
| `/lines/` | POST | `can_manage_production_lines` | Create new line |
| `/lines/<line_id>/` | PATCH | `can_manage_production_lines` | Update line |
| `/lines/<line_id>/` | DELETE | `can_manage_production_lines` | Soft-delete (sets `is_active=False`) |

**Create Request Body:**
```json
{
  "name": "Line 1 - Oil Filling",
  "description": "Edible oil filling line"
}
```

**Fields:**
| Field | Type | Constraints |
|-------|------|-------------|
| name | CharField(100) | Required, unique per company |
| description | TextField | Optional |
| is_active | Boolean | Default: true |

**Business Rules:**
- Name must be unique within the company (unique_together: company + name)
- Delete is a soft-delete — sets `is_active=False`, does not remove the record
- Lines cannot be hard-deleted if machines or runs reference them (PROTECT FK)

---

### 1.2 Machines

A machine belongs to a production line and has a type classification.

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/machines/` | GET | `can_view_production_run` | List machines (filter: `?line_id=`, `?machine_type=`, `?is_active=`) |
| `/machines/` | POST | `can_manage_machines` | Create machine |
| `/machines/<machine_id>/` | PATCH | `can_manage_machines` | Update machine |
| `/machines/<machine_id>/` | DELETE | `can_manage_machines` | Soft-delete |

**Create Request Body:**
```json
{
  "name": "Filler Machine A",
  "machine_type": "FILLER",
  "line_id": 1
}
```

**Machine Types (MachineType enum):**
| Value | Display |
|-------|---------|
| FILLER | Filler |
| CAPPER | Capper |
| CONVEYOR | Conveyor |
| LABELER | Labeler |
| CODING | Coding |
| SHRINK_PACK | Shrink Pack |
| STICKER_LABELER | Sticker Labeler |
| TAPPING_MACHINE | Tapping Machine |

**Business Rules:**
- Machine must reference an existing, company-owned production line
- Soft-delete on removal
- Machines are PROTECT-linked to breakdowns and runtimes

---

### 1.3 Machine Checklist Templates

Templates define recurring maintenance checklist tasks for each machine type.

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/checklist-templates/` | GET | `can_view_machine_checklist` | List templates (filter: `?machine_type=`, `?frequency=`) |
| `/checklist-templates/` | POST | `can_manage_checklist_templates` | Create template |
| `/checklist-templates/<id>/` | PATCH | `can_manage_checklist_templates` | Update |
| `/checklist-templates/<id>/` | DELETE | `can_manage_checklist_templates` | Hard-delete |

**Create Request Body:**
```json
{
  "machine_type": "FILLER",
  "task": "Check oil seal for leaks",
  "frequency": "DAILY",
  "sort_order": 1
}
```

**Frequency choices:** DAILY, WEEKLY, MONTHLY

---

## 2. SAP Integration — Fetching Production Orders

Before creating a production run, the operator selects a SAP production order.

### 2.1 List Released Orders

```
GET /sap/orders/
Permission: can_view_production_run
```

**How it works:**
1. `ProductionOrderReader` connects to SAP HANA via `hdbcli`
2. Queries `OWOR` table for orders with `Status='R'` (Released) and `RemainingQty > 0`
3. Returns live data — no caching

**Response:**
```json
[
  {
    "DocEntry": 1234,
    "DocNum": 5001,
    "ItemCode": "OIL-001",
    "ProdName": "Sunflower Oil 1L",
    "PlannedQty": 1000.0,
    "CmpltQty": 200.0,
    "RjctQty": 0.0,
    "RemainingQty": 800.0,
    "StartDate": "2026-03-15",
    "DueDate": "2026-03-20",
    "Warehouse": "WH01",
    "Status": "R"
  }
]
```

### 2.2 Order Detail with BOM Components

```
GET /sap/orders/<doc_entry>/
Permission: can_view_production_run
```

**Response:**
```json
{
  "header": { "DocEntry": 1234, "DocNum": 5001, ... },
  "components": [
    {
      "ItemCode": "RM-OIL-RAW",
      "ItemName": "Raw Sunflower Oil",
      "PlannedQty": 1100.0,
      "IssuedQty": 220.0,
      "Warehouse": "WH01",
      "UomCode": "LTR"
    }
  ]
}
```

**Error handling:** Returns 503 if SAP HANA is unreachable.

---

## 3. Line Clearance (Pre-Production)

Before production starts, the line must be inspected and cleared. This is a quality gate.

### 3.1 Flow Diagram

```
                      ┌──────────┐
                      │  CREATE  │
                      │  (DRAFT) │
                      └────┬─────┘
                           │
              9 standard checklist items
              auto-created (all start as N/A)
                           │
                           ▼
                 ┌──────────────────┐
                 │ FILL CHECKLIST   │
                 │ Mark each item   │
                 │ YES / NO / N/A   │
                 │ Add signatures   │
                 └────────┬─────────┘
                          │
                          ▼
                    ┌───────────┐     Validation:
                    │  SUBMIT   │────► All items must have result (not N/A)
                    │ (SUBMITTED│     At least one signature required
                    └─────┬─────┘
                          │
                     QA reviews
                          │
                ┌─────────┴──────────┐
                │                    │
                ▼                    ▼
          ┌──────────┐        ┌──────────────┐
          │ APPROVED │        │ NOT CLEARED  │
          │ (CLEARED)│        │              │
          └──────────┘        └──────────────┘
```

### 3.2 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/line-clearance/` | GET | `can_view_line_clearance` | List (filter: `?date=`, `?line_id=`, `?status=`) |
| `/line-clearance/` | POST | `can_create_line_clearance` | Create clearance |
| `/line-clearance/<id>/` | GET | `can_view_line_clearance` | Detail with items |
| `/line-clearance/<id>/` | PATCH | `can_create_line_clearance` | Update items and signatures |
| `/line-clearance/<id>/submit/` | POST | `can_create_line_clearance` | Submit for QA approval |
| `/line-clearance/<id>/approve/` | POST | `can_approve_line_clearance_qa` | QA approve/reject |

### 3.3 Create Clearance

```json
POST /line-clearance/
{
  "date": "2026-03-17",
  "line_id": 1,
  "sap_doc_entry": 1234,
  "document_id": "PRD-OIL-FRM-15-00-00-04"
}
```

**Auto-created items (9 standard checklist items):**
1. Previous product, labels and packaging materials removed
2. Machine/equipment cleaned and free from product residues
3. Utensils, scoops and accessories cleaned and available
4. Packaging area free from previous batch coding material
5. Work area (tables, conveyors, floor) cleaned and sanitized
6. Waste bins emptied and cleaned
7. Required packaging material verified against BOM
8. Coding machine updated with correct product/batch details
9. Environmental conditions (temperature/humidity) within limits

### 3.4 Update Clearance (Fill Checklist)

```json
PATCH /line-clearance/<id>/
{
  "items": [
    {"id": 1, "result": "YES", "remarks": ""},
    {"id": 2, "result": "YES", "remarks": "Cleaned with hot water"},
    {"id": 3, "result": "NO", "remarks": "Missing scoop — requested from store"}
  ],
  "production_supervisor_sign": "John Doe",
  "production_incharge_sign": "Jane Smith"
}
```

**Result choices:** YES, NO, NA

### 3.5 Submit Clearance

```json
POST /line-clearance/<id>/submit/
```
**Validations:**
- All 9 items must have a result (not N/A)
- At least one signature (supervisor or incharge) is required
- Only DRAFT clearances can be submitted

### 3.6 Approve/Reject Clearance

```json
POST /line-clearance/<id>/approve/
{
  "approved": true
}
```
- Only SUBMITTED clearances can be approved
- Sets `qa_approved`, `qa_approved_by`, `qa_approved_at`
- Status becomes CLEARED or NOT_CLEARED

---

## 4. Production Run Lifecycle

The production run is the **central entity** of the entire app. Everything else is attached to it.

### 4.1 Run Status Flow

```
     ┌────────┐     First data entry      ┌─────────────┐      Complete       ┌───────────┐
     │ DRAFT  │ ──────────────────────────►│ IN_PROGRESS │ ──────────────────►│ COMPLETED │
     └────────┘  (auto-transitions when    └─────────────┘                    └───────────┘
                  logs/run are updated)                                        (immutable)
```

**Key rule:** Once COMPLETED, no child records (logs, breakdowns, materials, etc.) can be added/edited.

### 4.2 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/` | GET | `can_view_production_run` | List runs (filter: `?date=`, `?line_id=`, `?status=`, `?sap_doc_entry=`) |
| `/runs/` | POST | `can_create_production_run` | Create run |
| `/runs/<run_id>/` | GET | `can_view_production_run` | Full detail (includes logs + breakdowns) |
| `/runs/<run_id>/` | PATCH | `can_edit_production_run` | Update run fields |
| `/runs/<run_id>/complete/` | POST | `can_complete_production_run` | Finalize run |

### 4.3 Create Production Run

```json
POST /runs/
{
  "sap_doc_entry": 1234,
  "line_id": 1,
  "date": "2026-03-17",
  "brand": "Sampooran Sunflower Oil",
  "pack": "1L x 12",
  "sap_order_no": "5001",
  "rated_speed": 120.00
}
```

**Business Logic (inside `create_run`):**
1. Validates the line exists and is active
2. **Auto-increments `run_number`**: Finds the last run for this (company, sap_doc_entry, date), increments by 1. First run of the day = 1.
3. Creates run with status = DRAFT
4. Unique constraint: (company, sap_doc_entry, date, run_number)

**Response includes the full run detail with empty logs and breakdowns.**

### 4.4 Update Production Run

```json
PATCH /runs/<run_id>/
{
  "brand": "Updated Brand",
  "rated_speed": 130.00
}
```

**Editable fields:** brand, pack, sap_order_no, rated_speed

**Business Rules:**
- Cannot edit a COMPLETED run
- If status is DRAFT, auto-transitions to IN_PROGRESS on first update

### 4.5 Complete Production Run

```json
POST /runs/<run_id>/complete/
```

**What happens (inside `complete_run`):**
1. Recomputes all summary totals by aggregating child records:
   - `total_production` = SUM of all hourly log `produced_cases`
   - `total_minutes_pe` = SUM of all hourly log `recd_minutes`
   - `total_breakdown_time` = SUM of all breakdown `breakdown_minutes`
   - `line_breakdown_time` = SUM of breakdowns where type=LINE
   - `external_breakdown_time` = SUM of breakdowns where type=EXTERNAL
   - `unrecorded_time` = 720 (12-hour shift) - total_minutes_pe - total_breakdown_time (min 0)
   - `total_minutes_me` = total_minutes_pe
2. Sets status to COMPLETED
3. Run becomes immutable — no further edits to any child data

### 4.6 Run Detail Response

```json
{
  "id": 1,
  "sap_doc_entry": 1234,
  "run_number": 1,
  "date": "2026-03-17",
  "line": 1,
  "line_name": "Line 1 - Oil Filling",
  "brand": "Sampooran Sunflower Oil",
  "pack": "1L x 12",
  "sap_order_no": "5001",
  "rated_speed": "120.00",
  "total_production": 960,
  "total_minutes_pe": 600,
  "total_minutes_me": 600,
  "total_breakdown_time": 45,
  "line_breakdown_time": 30,
  "external_breakdown_time": 15,
  "unrecorded_time": 75,
  "status": "IN_PROGRESS",
  "created_by": 5,
  "created_at": "2026-03-17T07:00:00Z",
  "updated_at": "2026-03-17T14:30:00Z",
  "logs": [ ... ],
  "breakdowns": [ ... ]
}
```

---

## 5. Hourly Production Logs

Operators record output every hour during the 12-hour production shift.

### 5.1 Pre-defined Time Slots

The system uses 12 fixed hourly slots covering 07:00 to 19:00:

| Slot | Start | End |
|------|-------|-----|
| 07:00-08:00 | 07:00 | 08:00 |
| 08:00-09:00 | 08:00 | 09:00 |
| 09:00-10:00 | 09:00 | 10:00 |
| 10:00-11:00 | 10:00 | 11:00 |
| 11:00-12:00 | 11:00 | 12:00 |
| 12:00-13:00 | 12:00 | 13:00 |
| 13:00-14:00 | 13:00 | 14:00 |
| 14:00-15:00 | 14:00 | 15:00 |
| 15:00-16:00 | 15:00 | 16:00 |
| 16:00-17:00 | 16:00 | 17:00 |
| 17:00-18:00 | 17:00 | 18:00 |
| 18:00-19:00 | 18:00 | 19:00 |

### 5.2 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/logs/` | GET | `can_view_production_log` | List all logs for run |
| `/runs/<run_id>/logs/` | POST | `can_edit_production_log` | Create/update logs (accepts array or single) |
| `/runs/<run_id>/logs/<log_id>/` | PATCH | `can_edit_production_log` | Update individual log |

### 5.3 Create/Update Hourly Logs (Bulk)

```json
POST /runs/<run_id>/logs/
[
  {
    "time_slot": "07:00-08:00",
    "time_start": "07:00",
    "time_end": "08:00",
    "produced_cases": 100,
    "machine_status": "RUNNING",
    "recd_minutes": 55,
    "breakdown_detail": "",
    "remarks": ""
  },
  {
    "time_slot": "08:00-09:00",
    "time_start": "08:00",
    "time_end": "09:00",
    "produced_cases": 0,
    "machine_status": "BREAKDOWN",
    "recd_minutes": 0,
    "breakdown_detail": "Filler nozzle jam",
    "remarks": "Maintenance called"
  }
]
```

**Machine Status choices:** RUNNING, IDLE, BREAKDOWN, CHANGEOVER

**Business Logic (inside `save_hourly_logs`):**
1. Cannot save to a COMPLETED run
2. Uses `update_or_create` keyed on (production_run, time_start) — allows re-sending same slot to update
3. After saving, **recomputes run totals** automatically
4. If run was DRAFT, auto-transitions to IN_PROGRESS

**Validation:**
- `produced_cases`: min 0
- `recd_minutes`: min 0, max 60 (1 hour max per slot)

---

## 6. Machine Breakdowns

Records downtime events for specific machines during a run.

### 6.1 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/breakdowns/` | GET | `can_view_breakdown` | List breakdowns for run |
| `/runs/<run_id>/breakdowns/` | POST | `can_create_breakdown` | Add breakdown |
| `/runs/<run_id>/breakdowns/<id>/` | PATCH | `can_edit_breakdown` | Update breakdown |
| `/runs/<run_id>/breakdowns/<id>/` | DELETE | `can_edit_breakdown` | Delete breakdown |

### 6.2 Create Breakdown

```json
POST /runs/<run_id>/breakdowns/
{
  "machine_id": 3,
  "start_time": "2026-03-17T09:15:00Z",
  "end_time": "2026-03-17T09:45:00Z",
  "breakdown_minutes": 30,
  "type": "LINE",
  "is_unrecovered": false,
  "reason": "Filler nozzle jam — oil leak on station 4",
  "remarks": "Maintenance replaced gasket"
}
```

**Breakdown types:**
| Value | Meaning |
|-------|---------|
| LINE | Breakdown within the production line (affects availability) |
| EXTERNAL | External factor breakdown (power cut, utility failure) |

**Business Logic (inside `add_breakdown`):**
1. Validates run is not COMPLETED
2. Validates machine belongs to the same production line as the run
3. **Auto-calculates `breakdown_minutes`** if not provided: `(end_time - start_time) / 60`
4. After saving, **recomputes run totals** (breakdown times aggregated by type)

---

## 7. Material Usage (Yield Tracking)

Tracks raw material consumption per batch during a run.

### 7.1 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/materials/` | GET | `can_view_material_usage` | List (filter: `?batch_number=`) |
| `/runs/<run_id>/materials/` | POST | `can_create_material_usage` | Add material records (array or single) |
| `/runs/<run_id>/materials/<id>/` | PATCH | `can_edit_material_usage` | Update record |

### 7.2 Create Material Usage

```json
POST /runs/<run_id>/materials/
[
  {
    "material_code": "RM-OIL-RAW",
    "material_name": "Raw Sunflower Oil",
    "opening_qty": 500.000,
    "issued_qty": 200.000,
    "closing_qty": 580.000,
    "uom": "LTR",
    "batch_number": 1
  }
]
```

**Business Logic:**
- `wastage_qty` is **auto-calculated**: `opening_qty + issued_qty - closing_qty`
- This formula represents: stock available + stock received - stock remaining = stock consumed/wasted
- `batch_number` range: 1-3 (represents batch/shift within the run)
- Recalculated on every update to `opening_qty`, `issued_qty`, or `closing_qty`

---

## 8. Machine Runtime

Tracks how long each machine type ran and was down during the run.

### 8.1 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/machine-runtime/` | GET | `can_view_machine_runtime` | List |
| `/runs/<run_id>/machine-runtime/` | POST | `can_create_machine_runtime` | Add (array or single) |
| `/runs/<run_id>/machine-runtime/<id>/` | PATCH | `can_create_machine_runtime` | Update |

### 8.2 Create Runtime Entry

```json
POST /runs/<run_id>/machine-runtime/
{
  "machine_id": 3,
  "machine_type": "FILLER",
  "runtime_minutes": 680,
  "downtime_minutes": 40,
  "remarks": "Short idle periods during shift change"
}
```

**Note:** `machine_id` is optional — you can track runtime by machine_type alone.

---

## 9. Manpower Tracking

Records staffing details per shift for a production run.

### 9.1 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/manpower/` | GET | `can_view_manpower` | List |
| `/runs/<run_id>/manpower/` | POST | `can_create_manpower` | Add/update (upsert by shift) |
| `/runs/<run_id>/manpower/<id>/` | PATCH | `can_create_manpower` | Update |

### 9.2 Create Manpower Entry

```json
POST /runs/<run_id>/manpower/
{
  "shift": "MORNING",
  "worker_count": 8,
  "supervisor": "Rajesh Kumar",
  "engineer": "Amit Sharma",
  "remarks": ""
}
```

**Shift choices:** MORNING, AFTERNOON, NIGHT

**Business Logic:** Uses `update_or_create` keyed on (production_run, shift) — unique_together constraint means one entry per shift per run.

---

## 10. Resource Tracking

Tracks all costs associated with a production run. **Every resource save/update/delete triggers `recalculate_run_cost()`** which updates the `ProductionRunCost` record.

### 10.1 Resource Types and Endpoints

All resource endpoints follow the same pattern:

| Resource | List/Create URL | Detail URL | Input Fields |
|----------|----------------|------------|--------------|
| Electricity | `/runs/<id>/resources/electricity/` | `.../<entry_id>/` | `units_consumed`, `rate_per_unit`, `description` |
| Water | `/runs/<id>/resources/water/` | `.../<entry_id>/` | `volume_consumed`, `rate_per_unit`, `description` |
| Gas | `/runs/<id>/resources/gas/` | `.../<entry_id>/` | `qty_consumed`, `rate_per_unit`, `description` |
| Compressed Air | `/runs/<id>/resources/compressed-air/` | `.../<entry_id>/` | `units_consumed`, `rate_per_unit`, `description` |
| Labour | `/runs/<id>/resources/labour/` | `.../<entry_id>/` | `worker_name`, `hours_worked`, `rate_per_hour` |
| Machine Cost | `/runs/<id>/resources/machine-costs/` | `.../<entry_id>/` | `machine_name`, `hours_used`, `rate_per_hour` |
| Overhead | `/runs/<id>/resources/overhead/` | `.../<entry_id>/` | `expense_name`, `amount` |

Each supports: **GET** (list), **POST** (create), **PATCH** (update), **DELETE** (remove)

### 10.2 Auto-Calculated `total_cost`

All resource models (except Overhead) auto-calculate `total_cost` in their `save()` method:

```
total_cost = qty_consumed × rate_per_unit
```

For Overhead, the `amount` field IS the cost directly.

### 10.3 Example — Electricity

```json
POST /runs/1/resources/electricity/
{
  "description": "Main meter reading",
  "units_consumed": 450.500,
  "rate_per_unit": 8.5000
}
```

**Response:**
```json
{
  "id": 1,
  "description": "Main meter reading",
  "units_consumed": "450.500",
  "rate_per_unit": "8.5000",
  "total_cost": "3829.25",
  "created_by": 5,
  "created_at": "2026-03-17T12:00:00Z"
}
```

---

## 11. Cost Calculation

### 11.1 How Cost is Computed

The `recalculate_run_cost()` function (called after every resource change) aggregates all costs:

```
raw_material_cost   = SUM(material_usages.total_cost or qty × unit_cost)
labour_cost         = SUM(labour_entries.total_cost)
machine_cost        = SUM(machine_cost_entries.total_cost)
electricity_cost    = SUM(electricity_usage.total_cost)
water_cost          = SUM(water_usage.total_cost)
gas_cost            = SUM(gas_usage.total_cost)
compressed_air_cost = SUM(compressed_air_usage.total_cost)
overhead_cost       = SUM(overhead_entries.amount)

total_cost = raw_material + labour + machine + electricity + water + gas + compressed_air + overhead
per_unit_cost = total_cost / total_production   (0 if no production)
```

Stored in `ProductionRunCost` (OneToOne with ProductionRun) via `update_or_create`.

### 11.2 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/cost/` | GET | `can_view_production_run` | Get cost breakdown for a run |
| `/costs/analytics/` | GET | `can_view_reports` | List costs across runs (filter: `?date_from=`, `?date_to=`, `?line=`) |

### 11.3 Cost Summary Response

```json
{
  "id": 1,
  "raw_material_cost": "0.00",
  "labour_cost": "4800.00",
  "machine_cost": "2400.00",
  "electricity_cost": "3829.25",
  "water_cost": "500.00",
  "gas_cost": "1200.00",
  "compressed_air_cost": "300.00",
  "overhead_cost": "1500.00",
  "total_cost": "14529.25",
  "produced_qty": "960.000",
  "per_unit_cost": "15.1346",
  "calculated_at": "2026-03-17T15:00:00Z"
}
```

---

## 12. Quality Checks

### 12.1 In-Process QC

Multiple QC checks can be performed during the run.

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/qc/inprocess/` | GET | `can_view_production_run` | List checks |
| `/runs/<run_id>/qc/inprocess/` | POST | `can_view_production_run` | Add check |
| `/runs/<run_id>/qc/inprocess/<id>/` | PATCH | `can_view_production_run` | Update |
| `/runs/<run_id>/qc/inprocess/<id>/` | DELETE | `can_view_production_run` | Delete |

**Create Request:**
```json
POST /runs/<run_id>/qc/inprocess/
{
  "checked_at": "2026-03-17T10:30:00Z",
  "parameter": "Fill Volume",
  "acceptable_min": 990.000,
  "acceptable_max": 1010.000,
  "actual_value": 1005.000,
  "result": "PASS",
  "remarks": ""
}
```

**Result choices:** PASS, FAIL, NA

### 12.2 Final QC

One final QC check per run (OneToOne relationship).

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/runs/<run_id>/qc/final/` | GET | `can_view_production_run` | Get final QC |
| `/runs/<run_id>/qc/final/` | POST | `can_view_production_run` | Create final QC (only once) |
| `/runs/<run_id>/qc/final/` | PATCH | `can_view_production_run` | Update final QC |

**Create Request:**
```json
POST /runs/<run_id>/qc/final/
{
  "checked_at": "2026-03-17T18:00:00Z",
  "overall_result": "PASS",
  "parameters": [
    {"name": "Fill Volume", "expected": "1000ml", "actual": "1005ml", "result": "PASS"},
    {"name": "Seal Integrity", "expected": "No leak", "actual": "No leak", "result": "PASS"},
    {"name": "Label Alignment", "expected": "<2mm offset", "actual": "1mm", "result": "PASS"}
  ],
  "remarks": "Batch approved for dispatch"
}
```

**Overall result choices:** PASS, FAIL, CONDITIONAL

**Business Rule:** Only one final QC per run. POST returns 400 if one already exists — use PATCH to update.

---

## 13. Waste Management (Multi-Level Approval)

Waste logs track material wastage and require a **4-level sequential approval chain**.

### 13.1 Approval Flow

```
 ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────────────────┐
 │  CREATE   │────►│ ENGINEER │────►│    AM    │────►│  STORE   │────►│     HOD        │
 │ (PENDING) │     │  SIGN    │     │  SIGN    │     │  SIGN    │     │    SIGN        │
 └──────────┘     └──────────┘     └──────────┘     └──────────┘     └────────────────┘
                   Status:          Status:          Status:          Status:
                   PARTIALLY        PARTIALLY        PARTIALLY        FULLY_APPROVED
                   _APPROVED        _APPROVED        _APPROVED
```

**Strict sequential order:**
- AM cannot sign until Engineer has signed
- Store cannot sign until AM has signed
- HOD cannot sign until Store has signed

### 13.2 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/waste/` | GET | `can_view_waste_log` | List (filter: `?run_id=`, `?approval_status=`) |
| `/waste/` | POST | `can_create_waste_log` | Create waste log |
| `/waste/<id>/` | GET | `can_view_waste_log` | Detail |
| `/waste/<id>/approve/engineer/` | POST | `can_approve_waste_engineer` | Engineer sign |
| `/waste/<id>/approve/am/` | POST | `can_approve_waste_am` | AM sign |
| `/waste/<id>/approve/store/` | POST | `can_approve_waste_store` | Store sign |
| `/waste/<id>/approve/hod/` | POST | `can_approve_waste_hod` | HOD sign |

### 13.3 Create Waste Log

```json
POST /waste/
{
  "production_run_id": 1,
  "material_code": "RM-OIL-RAW",
  "material_name": "Raw Sunflower Oil",
  "wastage_qty": 15.500,
  "uom": "LTR",
  "reason": "Spillage during tank transfer"
}
```

### 13.4 Approve (any level)

```json
POST /waste/<id>/approve/engineer/
{
  "sign": "Amit Sharma"
}
```

Each approval records: sign name, signed_by (user), signed_at (timestamp).

---

## 14. Machine Checklists

Maintenance teams use these to track daily/weekly/monthly machine inspections.

### 14.1 Endpoints

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/machine-checklists/` | GET | `can_view_machine_checklist` | List (filter: `?machine_id=`, `?month=`, `?year=`, `?frequency=`) |
| `/machine-checklists/` | POST | `can_create_machine_checklist` | Create entry |
| `/machine-checklists/bulk/` | POST | `can_create_machine_checklist` | Bulk upsert (array) |
| `/machine-checklists/<id>/` | PATCH | `can_create_machine_checklist` | Update entry |

### 14.2 Create Entry

```json
POST /machine-checklists/
{
  "machine_id": 3,
  "template_id": 5,
  "date": "2026-03-17",
  "status": "OK",
  "operator": "Ram Singh",
  "shift_incharge": "Sunil Verma",
  "remarks": ""
}
```

**Business Logic:**
- Copies `task_description` from template and `machine_type` from machine
- Auto-sets `month` and `year` from `date`
- Unique constraint: (machine, template, date) — one entry per machine per task per day
- Bulk endpoint uses `update_or_create` for idempotent upserts

**Status choices:** OK, NOT_OK, NA

---

## 15. Reports & Analytics

### 15.1 Standard Reports

| Endpoint | Method | Query Params | Description |
|----------|--------|--------------|-------------|
| `/reports/daily-production/` | GET | `date` (required), `line_id` | All runs for a date with logs and breakdowns |
| `/reports/yield/<run_id>/` | GET | — | Material usage, machine runtime, and manpower for one run |
| `/reports/line-clearance/` | GET | `date_from`, `date_to` | Clearance records in date range |
| `/reports/analytics/` | GET | `date_from`, `date_to`, `line_id` | Aggregated production analytics |

### 15.2 Analytics Response

```json
GET /reports/analytics/?date_from=2026-03-01&date_to=2026-03-17
{
  "total_runs": 45,
  "total_production": 43200,
  "total_pe_minutes": 27000,
  "total_breakdown_minutes": 2700,
  "total_line_breakdown_minutes": 1800,
  "total_external_breakdown_minutes": 900,
  "available_time_minutes": 32400,
  "operating_time_minutes": 29700,
  "availability_percent": 91.7
}
```

**Calculation:**
- `available_time = total_runs × 720` (12-hour shift in minutes)
- `operating_time = available_time - total_breakdown_minutes`
- `availability_percent = (operating_time / available_time) × 100`

### 15.3 OEE Analytics

```
GET /reports/analytics/oee/?date_from=2026-03-01&date_to=2026-03-17&line=1
```

Calculates **Overall Equipment Effectiveness** per run:

```
Availability = (720 - breakdown_minutes) / 720 × 100
Performance  = (actual_speed / rated_speed) × 100     (capped at 100%)
    where actual_speed = total_production / operating_minutes
Quality      = 100%   (default — no reject tracking yet)

OEE = (Availability × Performance × Quality) / 10000
```

**Response includes the standard analytics plus `per_run_oee[]`:**
```json
{
  "total_runs": 45,
  "availability_percent": 91.7,
  ...
  "per_run_oee": [
    {
      "run_id": 1,
      "run_number": 1,
      "date": "2026-03-17",
      "line": "Line 1",
      "availability": 93.8,
      "performance": 85.2,
      "quality": 100.0,
      "oee": 79.90
    }
  ]
}
```

### 15.4 Downtime Analytics

```
GET /reports/analytics/downtime/?date_from=2026-03-01&date_to=2026-03-17&machine=3
```

Aggregates breakdowns by reason:

```json
{
  "breakdowns": [
    {"reason": "Filler nozzle jam", "count": 12, "total_minutes": 360},
    {"reason": "Power fluctuation", "count": 5, "total_minutes": 150}
  ],
  "total_count": 17,
  "total_minutes": 510
}
```

### 15.5 Waste Analytics

```
GET /reports/analytics/waste/?date_from=2026-03-01&date_to=2026-03-17
```

```json
{
  "by_material": [
    {"material_name": "Raw Sunflower Oil", "uom": "LTR", "total_waste": "245.500", "count": 8},
    {"material_name": "PET Bottles 1L", "uom": "PCS", "total_waste": "120.000", "count": 3}
  ],
  "by_approval_status": [
    {"wastage_approval_status": "FULLY_APPROVED", "count": 6},
    {"wastage_approval_status": "PENDING", "count": 5}
  ],
  "total_waste_logs": 11
}
```

---

## 16. SAP Write-Back — Goods Receipt

After production is completed, the produced quantity is posted back to SAP.

### How it works (GoodsReceiptWriter)

```python
writer = GoodsReceiptWriter(company_code)
doc_entry = writer.post_goods_receipt(
    doc_entry=1234,        # SAP Production Order DocEntry
    item_code="OIL-001",   # Finished good code
    warehouse="WH01",      # Target warehouse
    qty=960,               # Produced quantity
    posting_date=date.today()
)
```

**SAP B1 Service Layer flow:**
1. POST `/b1s/v2/Login` to authenticate
2. POST `/b1s/v2/InventoryGenEntries` with payload:
   ```json
   {
     "DocDate": "2026-03-17",
     "Comments": "Production Execution — DocEntry 1234",
     "DocumentLines": [{
       "ItemCode": "OIL-001",
       "Quantity": 960,
       "WarehouseCode": "WH01",
       "BaseType": 202,
       "BaseEntry": 1234,
       "BaseLine": 0
     }]
   }
   ```
3. `BaseType=202` links the goods receipt to the production order
4. Returns the DocEntry of the created goods receipt document

---

## 17. Permission Matrix

All endpoints require `IsAuthenticated` + `HasCompanyContext`. Additional permissions:

| Area | View | Create/Edit | Special |
|------|------|-------------|---------|
| Production Lines | `can_view_production_run` | `can_manage_production_lines` | — |
| Machines | `can_view_production_run` | `can_manage_machines` | — |
| Checklist Templates | `can_view_machine_checklist` | `can_manage_checklist_templates` | — |
| Production Runs | `can_view_production_run` | `can_create_production_run` / `can_edit_production_run` | `can_complete_production_run` |
| Hourly Logs | `can_view_production_log` | `can_edit_production_log` | — |
| Breakdowns | `can_view_breakdown` | `can_create_breakdown` / `can_edit_breakdown` | — |
| Material Usage | `can_view_material_usage` | `can_create_material_usage` / `can_edit_material_usage` | — |
| Machine Runtime | `can_view_machine_runtime` | `can_create_machine_runtime` | — |
| Manpower | `can_view_manpower` | `can_create_manpower` | — |
| Line Clearance | `can_view_line_clearance` | `can_create_line_clearance` | `can_approve_line_clearance_qa` |
| Machine Checklists | `can_view_machine_checklist` | `can_create_machine_checklist` | — |
| Waste Logs | `can_view_waste_log` | `can_create_waste_log` | `can_approve_waste_engineer/am/store/hod` |
| Reports | `can_view_reports` | — | — |
| SAP Orders | `can_view_production_run` | — | — |

---

## 18. Complete Data Model

```
ProductionLine                    MachineChecklistTemplate
    │                                     │
    ├── Machine[]                         └── MachineChecklistEntry[]
    │       │                                  (unique: machine + template + date)
    │       ├── MachineBreakdown[]
    │       └── MachineRuntime[]
    │
    ├── ProductionRun[]  ◄── central entity, linked via sap_doc_entry to SAP OWOR
    │       │
    │       ├── ProductionLog[]              (12 hourly slots, unique: run + time_start)
    │       ├── MachineBreakdown[]           (LINE or EXTERNAL type)
    │       ├── ProductionMaterialUsage[]    (wastage auto-calculated)
    │       ├── MachineRuntime[]             (per machine type)
    │       ├── ProductionManpower[]         (unique: run + shift)
    │       ├── WasteLog[]                   (4-level approval chain)
    │       ├── InProcessQCCheck[]           (multiple per run)
    │       ├── FinalQCCheck                 (1:1, one per run)
    │       ├── ProductionRunCost            (1:1, auto-recalculated)
    │       │
    │       ├── ResourceElectricity[]
    │       ├── ResourceWater[]
    │       ├── ResourceGas[]
    │       ├── ResourceCompressedAir[]
    │       ├── ResourceLabour[]
    │       ├── ResourceMachineCost[]
    │       └── ResourceOverhead[]
    │
    └── LineClearance[]  ◄── also linked via sap_doc_entry
            │
            └── LineClearanceItem[]  (9 standard items auto-created)
```

---

## 19. Key Business Rules Summary

| Rule | Where Enforced |
|------|----------------|
| COMPLETED runs are immutable | `production_service.py` — every write method checks `run.status` |
| Run number auto-increments per (company, sap_doc_entry, date) | `create_run()` |
| DRAFT → IN_PROGRESS on first data entry | `update_run()`, `save_hourly_logs()` |
| Run totals recomputed on every log/breakdown change | `_recompute_run_totals()` called from multiple methods |
| 12-hour shift = 720 minutes | `_recompute_run_totals()` — hardcoded constant |
| Waste approval must be sequential | `approve_waste()` — checks previous level signed_at |
| Line clearance items must all be resolved before submit | `submit_clearance()` — checks for N/A results |
| Cost recalculated on every resource change | `recalculate_run_cost()` called in all resource views |
| Resource total_cost auto-calculated in model.save() | Resource model `save()` overrides |
| Machine must belong to run's production line | `add_breakdown()` — validates machine.line_id == run.line_id |
| One final QC per run | `FinalQCCheckAPI.post()` — checks existence first |
| One manpower entry per shift per run | unique_together on ProductionManpower |
| Delete = soft-delete for Lines and Machines | `delete_line()`, `delete_machine()` set is_active=False |
