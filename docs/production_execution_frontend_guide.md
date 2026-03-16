# Production Execution Module — Frontend Integration Guide

## Base URL

```
/api/v1/production-execution
```

## Authentication

All API calls require:
```
Authorization: Bearer <jwt_token>
Company-Code: <company_code>
Content-Type: application/json
```

---

## Master Data

### Production Lines

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/lines/` | List all lines |
| POST | `/lines/` | Create line |
| GET | `/lines/{id}/` | Get line detail |
| PATCH | `/lines/{id}/` | Update line |
| DELETE | `/lines/{id}/` | Deactivate line |

**Create line request:**
```json
{
    "name": "Line-1",
    "description": "Main production line"
}
```

**Filter:** `?is_active=true|false`

### Machines

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/machines/` | List machines |
| POST | `/machines/` | Create machine |
| GET | `/machines/{id}/` | Get detail |
| PATCH | `/machines/{id}/` | Update |
| DELETE | `/machines/{id}/` | Deactivate |

**Create machine request:**
```json
{
    "name": "10-Head Filler",
    "machine_type": "FILLER",
    "line_id": 1
}
```

**Machine types:** `FILLER`, `CAPPER`, `CONVEYOR`, `LABELER`, `CODING`, `SHRINK_PACK`, `STICKER_LABELER`, `TAPPING_MACHINE`

**Filter:** `?line_id=1`, `?machine_type=FILLER`

### Checklist Templates

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/checklist-templates/` | List |
| POST | `/checklist-templates/` | Create |
| GET | `/checklist-templates/{id}/` | Detail |
| PATCH | `/checklist-templates/{id}/` | Update |
| DELETE | `/checklist-templates/{id}/` | Delete |

**Create request:**
```json
{
    "machine_type": "FILLER",
    "task": "Check oil level",
    "frequency": "DAILY",
    "sort_order": 1
}
```

---

## Production Runs

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/runs/` | List all runs |
| POST | `/runs/` | Create run |
| GET | `/runs/{id}/` | Get detail (includes logs & breakdowns) |
| PATCH | `/runs/{id}/` | Update run |
| DELETE | `/runs/{id}/` | Delete run |
| POST | `/runs/{id}/complete/` | Complete run |

**Create run request:**
```json
{
    "sap_doc_entry": 100,
    "line_id": 1,
    "date": "2026-03-16",
    "brand": "Brand A",
    "pack": "1L PET",
    "sap_order_no": "WOR-1001",
    "rated_speed": "150.00"
}
```

> `sap_doc_entry` is the SAP OWOR `DocEntry` from `GET /sap/orders/`. Production planning is managed entirely in SAP — there is no local production plan.

**List response fields:** `id`, `sap_doc_entry`, `run_number`, `date`, `line`, `line_name`, `brand`, `pack`, `sap_order_no`, `rated_speed`, `total_production`, `total_breakdown_time`, `status`, `created_by`, `created_at`

**Status values:** `DRAFT`, `IN_PROGRESS`, `COMPLETED`

---

## SAP Production Orders (Proxy)

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/sap/orders/` | List released production orders |
| GET | `/sap/orders/{doc_entry}/` | Get order detail with components |

Returns SAP data directly. Returns `503` if SAP is unavailable.

**List response shape:**
```json
[
    {
        "DocEntry": 100,
        "DocNum": 1001,
        "ItemCode": "FG-OIL-1L",
        "ItemName": "Oil 1 Litre",
        "PlannedQty": 5000.0,
        "CmpltQty": 0.0,
        "RjctQty": 0.0,
        "RemainingQty": 5000.0,
        "StartDate": "2026-03-15",
        "DueDate": "2026-03-18",
        "Warehouse": "WH-01",
        "Status": "R"
    }
]
```

**Detail response shape:**
```json
{
    "header": { ... },
    "components": [
        {
            "ItemCode": "RM-001",
            "ItemName": "Coconut Oil",
            "PlannedQty": 600.0,
            "IssuedQty": 0.0,
            "Warehouse": "WH-RM",
            "UomCode": "KG"
        }
    ]
}
```

---

## Hourly Production Logs

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/runs/{run_id}/logs/` | List logs |
| POST | `/runs/{run_id}/logs/` | Create log |
| GET | `/runs/{run_id}/logs/{id}/` | Get log |
| PATCH | `/runs/{run_id}/logs/{id}/` | Update |
| DELETE | `/runs/{run_id}/logs/{id}/` | Delete |

**Create request:**
```json
{
    "time_slot": "08:00-09:00",
    "time_start": "08:00:00",
    "time_end": "09:00:00",
    "produced_cases": 150,
    "machine_status": "RUNNING",
    "recd_minutes": 60,
    "breakdown_detail": "",
    "remarks": ""
}
```

**Machine status values:** `RUNNING`, `IDLE`, `BREAKDOWN`, `CHANGEOVER`

---

## Machine Breakdowns

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/runs/{run_id}/breakdowns/` | List |
| POST | `/runs/{run_id}/breakdowns/` | Create |
| GET | `/runs/{run_id}/breakdowns/{id}/` | Detail |
| PATCH | `/runs/{run_id}/breakdowns/{id}/` | Update |
| DELETE | `/runs/{run_id}/breakdowns/{id}/` | Delete |

**Create request:**
```json
{
    "machine_id": 1,
    "start_time": "2026-03-16T08:30:00Z",
    "end_time": "2026-03-16T09:00:00Z",
    "breakdown_minutes": 30,
    "type": "LINE",
    "reason": "Motor bearing failure",
    "remarks": "",
    "is_unrecovered": false
}
```

**Type values:** `LINE`, `EXTERNAL`

---

## Material Usage

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/runs/{run_id}/materials/` | List |
| POST | `/runs/{run_id}/materials/` | Create |
| GET | `/runs/{run_id}/materials/{id}/` | Detail |
| PATCH | `/runs/{run_id}/materials/{id}/` | Update |
| DELETE | `/runs/{run_id}/materials/{id}/` | Delete |

**Create request:**
```json
{
    "material_code": "RM-001",
    "material_name": "Coconut Oil",
    "opening_qty": "100.000",
    "issued_qty": "50.000",
    "closing_qty": "20.000",
    "uom": "KG",
    "batch_number": 1
}
```

`wastage_qty` is auto-calculated as `opening_qty + issued_qty - closing_qty`.

---

## Machine Runtime

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/runs/{run_id}/machine-runtime/` | List |
| POST | `/runs/{run_id}/machine-runtime/` | Create |
| PATCH | `/runs/{run_id}/machine-runtime/{id}/` | Update |
| DELETE | `/runs/{run_id}/machine-runtime/{id}/` | Delete |

**Create request:**
```json
{
    "machine_id": 1,
    "machine_type": "FILLER",
    "runtime_minutes": 480,
    "downtime_minutes": 30,
    "remarks": ""
}
```

---

## Manpower

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/runs/{run_id}/manpower/` | List |
| POST | `/runs/{run_id}/manpower/` | Create |
| PATCH | `/runs/{run_id}/manpower/{id}/` | Update |
| DELETE | `/runs/{run_id}/manpower/{id}/` | Delete |

**Create request:**
```json
{
    "shift": "MORNING",
    "worker_count": 12,
    "supervisor": "John Doe",
    "engineer": "Jane Smith",
    "remarks": ""
}
```

**Shift values:** `MORNING`, `AFTERNOON`, `NIGHT`

---

## Line Clearance

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/line-clearance/` | List |
| POST | `/line-clearance/` | Create |
| GET | `/line-clearance/{id}/` | Detail (with items) |
| PATCH | `/line-clearance/{id}/` | Update items/signatures |
| POST | `/line-clearance/{id}/submit/` | Submit for QA review |
| POST | `/line-clearance/{id}/approve/` | QA approve/reject |

---

## Machine Checklists

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/machine-checklists/` | List |
| POST | `/machine-checklists/` | Create entry |
| POST | `/machine-checklists/bulk/` | Bulk create |
| GET | `/machine-checklists/{id}/` | Detail |
| PATCH | `/machine-checklists/{id}/` | Update |

---

## Waste Logs

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/waste/` | List |
| POST | `/waste/` | Create |
| GET | `/waste/{id}/` | Detail |
| PATCH | `/waste/{id}/` | Update |
| DELETE | `/waste/{id}/` | Delete |
| POST | `/waste/{id}/approve/engineer/` | Engineer sign |
| POST | `/waste/{id}/approve/am/` | AM sign |
| POST | `/waste/{id}/approve/store/` | Store sign |
| POST | `/waste/{id}/approve/hod/` | HOD sign |

**Approval request body:**
```json
{ "sign": "Name / Designation" }
```

---

## Resource Tracking

All resource endpoints follow the same pattern:

### Electricity
```
GET  /runs/{run_id}/resources/electricity/
POST /runs/{run_id}/resources/electricity/
PATCH /runs/{run_id}/resources/electricity/{id}/
DELETE /runs/{run_id}/resources/electricity/{id}/
```
**Request body:**
```json
{
    "description": "Main line",
    "units_consumed": "150.500",
    "rate_per_unit": "8.5000"
}
```

### Water
```
GET/POST /runs/{run_id}/resources/water/
PATCH/DELETE /runs/{run_id}/resources/water/{id}/
```
**Request body:**
```json
{
    "description": "Process water",
    "volume_consumed": "500.000",
    "rate_per_unit": "2.0000"
}
```

### Gas
```
GET/POST /runs/{run_id}/resources/gas/
PATCH/DELETE /runs/{run_id}/resources/gas/{id}/
```
**Request body:**
```json
{
    "description": "LPG",
    "qty_consumed": "20.000",
    "rate_per_unit": "50.0000"
}
```

### Compressed Air
```
GET/POST /runs/{run_id}/resources/compressed-air/
PATCH/DELETE /runs/{run_id}/resources/compressed-air/{id}/
```
**Request body:**
```json
{
    "description": "Compressor A",
    "units_consumed": "200.000",
    "rate_per_unit": "1.5000"
}
```

### Labour
```
GET/POST /runs/{run_id}/resources/labour/
PATCH/DELETE /runs/{run_id}/resources/labour/{id}/
```
**Request body:**
```json
{
    "worker_name": "Ramesh Kumar",
    "hours_worked": "8.00",
    "rate_per_hour": "150.0000"
}
```

### Machine Cost
```
GET/POST /runs/{run_id}/resources/machine-costs/
PATCH/DELETE /runs/{run_id}/resources/machine-costs/{id}/
```
**Request body:**
```json
{
    "machine_name": "10-Head Filler",
    "hours_used": "8.00",
    "rate_per_hour": "500.0000"
}
```

### Overhead
```
GET/POST /runs/{run_id}/resources/overhead/
PATCH/DELETE /runs/{run_id}/resources/overhead/{id}/
```
**Request body:**
```json
{
    "expense_name": "Factory Rent (apportioned)",
    "amount": "5000.00"
}
```

**All resource response bodies include `total_cost` (auto-computed).**

---

## Cost Summary

```
GET /runs/{run_id}/cost/
```

**Response `200 OK`:**
```json
{
    "id": 1,
    "raw_material_cost": "0.00",
    "labour_cost": "1200.00",
    "machine_cost": "4000.00",
    "electricity_cost": "1279.25",
    "water_cost": "1000.00",
    "gas_cost": "1000.00",
    "compressed_air_cost": "300.00",
    "overhead_cost": "5000.00",
    "total_cost": "13779.25",
    "produced_qty": "1000.000",
    "per_unit_cost": "13.7793",
    "calculated_at": "2026-03-16T17:00:00Z"
}
```

Returns `404` if no resources recorded yet.

### Cost Analytics

```
GET /costs/analytics/?date_from=2026-03-01&date_to=2026-03-31&line=1
```

Returns list of `ProductionRunCost` objects.

---

## QC Checks

### In-Process QC

```
GET  /runs/{run_id}/qc/inprocess/
POST /runs/{run_id}/qc/inprocess/
PATCH /runs/{run_id}/qc/inprocess/{check_id}/
DELETE /runs/{run_id}/qc/inprocess/{check_id}/
```

**Create request:**
```json
{
    "checked_at": "2026-03-16T10:30:00Z",
    "parameter": "Fill Weight",
    "acceptable_min": "99.500",
    "acceptable_max": "100.500",
    "actual_value": "100.100",
    "result": "PASS",
    "remarks": "Within spec"
}
```

**Result values:** `PASS`, `FAIL`, `NA`

### Final QC

```
GET   /runs/{run_id}/qc/final/
POST  /runs/{run_id}/qc/final/
PATCH /runs/{run_id}/qc/final/
```

**Create request:**
```json
{
    "checked_at": "2026-03-16T17:00:00Z",
    "overall_result": "PASS",
    "parameters": [
        {
            "name": "Fill Weight",
            "expected": "100 ± 0.5g",
            "actual": "99.8g",
            "result": "PASS"
        }
    ],
    "remarks": "Batch released."
}
```

**Overall result values:** `PASS`, `FAIL`, `CONDITIONAL`

Only one Final QC allowed per run. `POST` returns `400` if already exists. Use `PATCH` to update.

---

## Reports & Analytics

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/reports/daily-production/` | Daily production summary |
| GET | `/reports/yield/{run_id}/` | Yield report for a run |
| GET | `/reports/line-clearance/` | Line clearance report |
| GET | `/reports/analytics/` | General analytics |
| GET | `/reports/analytics/oee/` | OEE analytics |
| GET | `/reports/analytics/downtime/` | Downtime analysis by reason |
| GET | `/reports/analytics/waste/` | Waste analysis by material |

### OEE Analytics Response

```json
{
    "per_run_oee": [
        {
            "run_id": 1,
            "run_number": 1,
            "date": "2026-03-16",
            "line": "Line-1",
            "availability": 95.8,
            "performance": 87.3,
            "quality": 100.0,
            "oee": 83.6
        }
    ]
}
```

**Common query params for analytics:** `date_from`, `date_to`, `line`

### Downtime Analytics Response

```json
{
    "breakdowns": [
        {
            "reason": "Motor failure",
            "count": 3,
            "total_minutes": 120
        }
    ],
    "total_count": 3,
    "total_minutes": 120
}
```

### Waste Analytics Response

```json
{
    "by_material": [
        {
            "material_name": "Palm Oil",
            "uom": "KG",
            "total_waste": "25.500",
            "count": 3
        }
    ],
    "by_approval_status": [
        {"wastage_approval_status": "PENDING", "count": 2},
        {"wastage_approval_status": "FULLY_APPROVED", "count": 1}
    ],
    "total_waste_logs": 3
}
```

---

## Example Flows

### Flow 1: Start a Production Run

> Production planning is done entirely in SAP. Use `GET /sap/orders/` to fetch released SAP production orders, then link them to runs via `sap_doc_entry`.

```
1. GET /sap/orders/          → fetch released SAP production orders (OWOR)
2. POST /runs/               → create run with sap_doc_entry from SAP order
3. POST /line-clearance/     → create line clearance for the run (optional)
4. POST /runs/{id}/logs/     → log hourly production (repeat each hour)
5. POST /runs/{id}/breakdowns/  → log breakdowns (if any)
6. POST /runs/{id}/complete/ → mark complete
```

### Flow 2: Record Resource Costs

```
1. POST /runs/{id}/resources/electricity/
2. POST /runs/{id}/resources/water/
3. POST /runs/{id}/resources/labour/   (one per worker)
4. POST /runs/{id}/resources/machine-costs/
5. POST /runs/{id}/resources/overhead/
6. GET  /runs/{id}/cost/    → view auto-calculated total
```

### Flow 3: QC Workflow

```
1. POST /runs/{id}/qc/inprocess/  → record parameter checks during run
   (repeat at each checkpoint)
2. POST /runs/{id}/qc/final/      → record final batch disposition
3. POST /runs/{id}/complete/      → complete the run
```

### Flow 4: Waste Approval Chain

```
1. POST /waste/                            → create waste log
2. POST /waste/{id}/approve/engineer/     → engineer signs
3. POST /waste/{id}/approve/am/           → AM signs
4. POST /waste/{id}/approve/store/        → store signs
5. POST /waste/{id}/approve/hod/          → HOD signs → FULLY_APPROVED
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | Deleted (no content) |
| 400 | Bad request / validation error |
| 401 | Not authenticated |
| 403 | Permission denied |
| 404 | Not found |
| 503 | SAP unavailable |

---

## Permissions Reference

| Permission | Required for |
|-----------|-------------|
| `can_view_production_run` | Read runs, logs, QC, cost |
| `can_create_production_run` | Create runs |
| `can_edit_production_run` | Update runs |
| `can_complete_production_run` | Complete runs |
| `can_create_material_usage` | All resource tracking endpoints |
| `can_view_reports` | Analytics, OEE, downtime, waste, cost analytics |
| `can_create_waste_log` | Create waste logs |
| `can_approve_waste_engineer/am/store/hod` | Each approval level |
