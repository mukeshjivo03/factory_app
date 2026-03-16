# Cost Management Guide

## Overview

The Cost Management module automatically aggregates all resource costs for a Production Run and computes a `ProductionRunCost` summary including per-unit cost.

## Cost Components

| Component | Source Model | Related Name |
|-----------|-------------|-------------|
| Raw Material | `ProductionMaterialUsage` | `material_usages` |
| Labour | `ResourceLabour` | `labour_entries` |
| Machine | `ResourceMachineCost` | `machine_cost_entries` |
| Electricity | `ResourceElectricity` | `electricity_usage` |
| Water | `ResourceWater` | `water_usage` |
| Gas | `ResourceGas` | `gas_usage` |
| Compressed Air | `ResourceCompressedAir` | `compressed_air_usage` |
| Overhead | `ResourceOverhead` | `overhead_entries` |

## How Costs Are Calculated

1. Each resource model has a `save()` override that calculates `total_cost`:
   - `total_cost = qty * rate`
2. After any resource create/update/delete, `recalculate_run_cost(run)` is called
3. This sums all component costs, computes total, and saves to `ProductionRunCost`

## Cost Summary Endpoint

```
GET /api/v1/production-execution/runs/{run_id}/cost/
```

Response `200 OK`:
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

Returns `404` if no resources have been recorded yet.

## Cost Analytics Endpoint

For cross-run cost analysis:

```
GET /api/v1/production-execution/costs/analytics/
```

Query parameters:
- `date_from` (YYYY-MM-DD)
- `date_to` (YYYY-MM-DD)
- `line` (line ID)

Returns a list of `ProductionRunCost` records matching the filter.

## Raw Material Cost Note

Raw material cost from `ProductionMaterialUsage` is only included if the material entry has a `unit_cost` field. Since the base model does not store unit_cost by default, raw material cost defaults to 0 unless manually tracked through a separate cost entry.

## Permissions Required

- `can_view_production_run` — to view cost summary
- `can_view_reports` — for cost analytics
