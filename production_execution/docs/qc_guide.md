# QC Checks Guide

## Overview

The QC module provides two levels of quality control for a Production Run:
1. **In-Process QC Checks** — multiple checks throughout the run
2. **Final QC Check** — a single consolidated result at run completion

## In-Process QC Checks

In-process checks record parameter measurements at specific timestamps.

### List checks
```
GET /api/v1/production-execution/runs/{run_id}/qc/inprocess/
```

### Create check
```
POST /api/v1/production-execution/runs/{run_id}/qc/inprocess/
Content-Type: application/json

{
    "checked_at": "2026-03-16T10:30:00Z",
    "parameter": "Fill Weight",
    "acceptable_min": "99.500",
    "acceptable_max": "100.500",
    "actual_value": "100.100",
    "result": "PASS",
    "remarks": "Within specification"
}
```

Response `201 Created`:
```json
{
    "id": 1,
    "checked_at": "2026-03-16T10:30:00Z",
    "parameter": "Fill Weight",
    "acceptable_min": "99.500",
    "acceptable_max": "100.500",
    "actual_value": "100.100",
    "result": "PASS",
    "remarks": "Within specification",
    "checked_by": 1,
    "created_at": "2026-03-16T10:30:00Z",
    "updated_at": "2026-03-16T10:30:00Z"
}
```

### Result choices
- `PASS` — parameter within spec
- `FAIL` — parameter out of spec
- `NA` — not applicable / not yet evaluated

### Update check
```
PATCH /api/v1/production-execution/runs/{run_id}/qc/inprocess/{check_id}/
```
Updatable fields: `checked_at`, `parameter`, `acceptable_min`, `acceptable_max`, `actual_value`, `result`, `remarks`

### Delete check
```
DELETE /api/v1/production-execution/runs/{run_id}/qc/inprocess/{check_id}/
```
Returns `204 No Content`

## Final QC Check

One per production run. Records the overall quality disposition.

### Get final QC
```
GET /api/v1/production-execution/runs/{run_id}/qc/final/
```
Returns `404` if not yet created.

### Create final QC
```
POST /api/v1/production-execution/runs/{run_id}/qc/final/
Content-Type: application/json

{
    "checked_at": "2026-03-16T17:00:00Z",
    "overall_result": "PASS",
    "parameters": [
        {
            "name": "Fill Weight",
            "expected": "100 ± 0.5",
            "actual": "99.8",
            "result": "PASS"
        },
        {
            "name": "pH",
            "expected": "6.5 - 7.0",
            "actual": "6.7",
            "result": "PASS"
        }
    ],
    "remarks": "All parameters within specification. Batch released."
}
```

Returns `400` if Final QC already exists for the run.

### Overall result choices
- `PASS` — batch released
- `FAIL` — batch rejected
- `CONDITIONAL` — batch conditionally released pending deviation review

### Update final QC
```
PATCH /api/v1/production-execution/runs/{run_id}/qc/final/

{
    "overall_result": "CONDITIONAL",
    "remarks": "Deviation noted in fill weight at hour 6. Accepted under deviation No. DEV-2026-001."
}
```

Updatable fields: `checked_at`, `overall_result`, `parameters`, `remarks`

## Permissions Required

Both endpoints require `can_view_production_run` permission.
