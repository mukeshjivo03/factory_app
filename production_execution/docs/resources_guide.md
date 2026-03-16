# Resource Tracking Submodule Guide

## Overview

The Resource Tracking submodule allows recording of all production-related resource consumption against a Production Run. Each resource type has its own endpoint and automatically calculates `total_cost` from quantity and rate. After any create/update/delete operation, the run's `ProductionRunCost` summary is recalculated.

## Resource Types

| Type | Unit Field | Endpoint |
|------|-----------|----------|
| Electricity | `units_consumed` | `/runs/{run_id}/resources/electricity/` |
| Water | `volume_consumed` | `/runs/{run_id}/resources/water/` |
| Gas | `qty_consumed` | `/runs/{run_id}/resources/gas/` |
| Compressed Air | `units_consumed` | `/runs/{run_id}/resources/compressed-air/` |
| Labour | `hours_worked` | `/runs/{run_id}/resources/labour/` |
| Machine Cost | `hours_used` | `/runs/{run_id}/resources/machine-costs/` |
| Overhead | `amount` | `/runs/{run_id}/resources/overhead/` |

## Authentication

All endpoints require:
- `Authorization: Bearer <token>`
- `Company-Code: <company_code>`

## Electricity

### List entries
```
GET /api/v1/production-execution/runs/{run_id}/resources/electricity/
```

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/electricity/
Content-Type: application/json

{
    "description": "Main line supply",
    "units_consumed": "150.500",
    "rate_per_unit": "8.5000"
}
```

Response `201 Created`:
```json
{
    "id": 1,
    "description": "Main line supply",
    "units_consumed": "150.500",
    "rate_per_unit": "8.5000",
    "total_cost": "1279.25",
    "created_by": 1,
    "created_at": "2026-03-16T10:00:00Z",
    "updated_at": "2026-03-16T10:00:00Z"
}
```

### Update entry
```
PATCH /api/v1/production-execution/runs/{run_id}/resources/electricity/{entry_id}/
```
Fields: `description`, `units_consumed`, `rate_per_unit`

### Delete entry
```
DELETE /api/v1/production-execution/runs/{run_id}/resources/electricity/{entry_id}/
```
Returns `204 No Content`

## Water

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/water/

{
    "description": "Process water",
    "volume_consumed": "500.000",
    "rate_per_unit": "2.0000"
}
```

## Gas

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/gas/

{
    "description": "LPG cylinder",
    "qty_consumed": "20.000",
    "rate_per_unit": "50.0000"
}
```

## Compressed Air

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/compressed-air/

{
    "description": "Compressor A output",
    "units_consumed": "200.000",
    "rate_per_unit": "1.5000"
}
```

## Labour

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/labour/

{
    "worker_name": "Ramesh Kumar",
    "hours_worked": "8.00",
    "rate_per_hour": "150.0000"
}
```

## Machine Cost

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/machine-costs/

{
    "machine_name": "10-Head Filler",
    "hours_used": "8.00",
    "rate_per_hour": "500.0000"
}
```

## Overhead

### Create entry
```
POST /api/v1/production-execution/runs/{run_id}/resources/overhead/

{
    "expense_name": "Factory Rent (apportioned)",
    "amount": "5000.00"
}
```

Note: Overhead does not have a `rate_per_unit` — you enter the total `amount` directly.

## Cost Recalculation

After every resource create/update/delete, the system calls `recalculate_run_cost()` which:
1. Sums all resource costs for the run
2. Gets `total_production` from the run
3. Computes `per_unit_cost = total_cost / total_production`
4. Upserts `ProductionRunCost`

To view the cost summary:
```
GET /api/v1/production-execution/runs/{run_id}/cost/
```

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Validation error (missing required field) |
| 401 | Not authenticated |
| 403 | Permission denied |
| 404 | Run or entry not found |
