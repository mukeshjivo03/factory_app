# Frontend Integration Guide — SAP Production Receipt

This guide explains how the frontend should integrate with the SAP Production Receipt feature. When a production run is completed, the system automatically posts a Goods Receipt to SAP B1 and tracks the sync status.

---

## New API Response Fields

After this integration, all production run responses (`list` and `detail`) include three new fields:

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `sap_receipt_doc_entry` | `int \| null` | e.g. `5678` or `null` | SAP Goods Receipt document number (set on success) |
| `sap_sync_status` | `string` | `NOT_APPLICABLE`, `PENDING`, `SUCCESS`, `FAILED` | Current SAP sync state |
| `sap_sync_error` | `string` | Error message or `""` | Error details when sync fails |

### Status Meanings

| Status | When It Occurs | Frontend Action |
|--------|----------------|-----------------|
| `NOT_APPLICABLE` | Run has no `sap_doc_entry` (manual/non-SAP run), or net qty <= 0 | Show nothing or grey "N/A" badge |
| `PENDING` | Sync is in progress (brief, during API call) | Show spinner/loading indicator |
| `SUCCESS` | Goods receipt posted to SAP successfully | Show green success badge with `sap_receipt_doc_entry` |
| `FAILED` | SAP posting failed (auth, network, validation error) | Show red error badge + retry button |

---

## API Endpoints

### 1. Complete Production Run (existing, updated response)

**Endpoint:** `POST /api/production-execution/runs/{run_id}/complete/`

**Request Body:**
```json
{
    "total_production": 500.0
}
```

**Response (200 OK):**
```json
{
    "id": 42,
    "sap_doc_entry": 1234,
    "run_number": 1,
    "date": "2026-03-28",
    "line": 1,
    "line_name": "Line A",
    "product": "Finished Good A",
    "rated_speed": "120.00",
    "labour_count": 5,
    "other_manpower_count": 2,
    "supervisor": "John",
    "operators": "Alice, Bob",
    "total_production": "500.0",
    "total_running_minutes": 360,
    "total_breakdown_time": 30,
    "rejected_qty": "10.0",
    "reworked_qty": "5.0",
    "sap_receipt_doc_entry": 5678,
    "sap_sync_status": "SUCCESS",
    "sap_sync_error": "",
    "status": "COMPLETED",
    "created_by": 1,
    "created_at": "2026-03-28T08:00:00Z",
    "updated_at": "2026-03-28T14:00:00Z",
    "segments": [],
    "breakdowns": [],
    "machine_ids": [1, 2]
}
```

**When SAP sync fails, the run is still COMPLETED but:**
```json
{
    "status": "COMPLETED",
    "sap_sync_status": "FAILED",
    "sap_sync_error": "Failed to post GR to SAP: Cannot find Production Order 1234",
    "sap_receipt_doc_entry": null
}
```

### 2. Retry SAP Goods Receipt (new endpoint)

**Endpoint:** `POST /api/production-execution/runs/{run_id}/retry-sap-receipt/`

**Request Body:** (empty)

**Response (200 OK):** Full production run detail (same as complete response)

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| `400` | Run not completed | `{"detail": "Can only retry SAP sync for completed runs."}` |
| `400` | Already synced | `{"detail": "SAP goods receipt already posted successfully."}` |
| `400` | No SAP link | `{"detail": "Run is not linked to a SAP production order."}` |

**Permission:** Same as completing a run (`can_complete_production_run`)

### 3. List Production Runs (existing, updated response)

**Endpoint:** `GET /api/production-execution/runs/`

Each item in the list now includes `sap_receipt_doc_entry`, `sap_sync_status`, and `sap_sync_error`.

---

## Frontend Implementation Guide

### 1. Run Completion Flow

When the operator clicks "Complete Run":

```
┌──────────────┐     POST /complete/     ┌──────────────────┐
│  Complete     │ ──────────────────────> │  Backend:        │
│  Button       │                         │  1. Mark complete│
│               │                         │  2. Post to SAP  │
│               │ <────────────────────── │  3. Return result│
│  Show result  │     Response            └──────────────────┘
└──────────────┘
```

**Frontend pseudocode:**
```javascript
async function completeRun(runId, totalProduction) {
    const response = await api.post(
        `/api/production-execution/runs/${runId}/complete/`,
        { total_production: totalProduction }
    );

    const run = response.data;

    // Run is always COMPLETED at this point
    showSuccessMessage("Production run completed!");

    // Handle SAP sync status separately
    if (run.sap_sync_status === "SUCCESS") {
        showSAPSuccess(`SAP Receipt: ${run.sap_receipt_doc_entry}`);
    } else if (run.sap_sync_status === "FAILED") {
        showSAPWarning(run.sap_sync_error);
        // Show retry button
    }
    // NOT_APPLICABLE — no SAP badge needed
}
```

### 2. SAP Status Badge Component

Display SAP sync status on the run list and detail pages:

```
┌─────────────────────────────────────────────────────────────┐
│ Run #1 — 2026-03-28 — Line A                               │
│ Product: Finished Good A     Total: 500 cases               │
│ Status: ✅ COMPLETED                                        │
│ SAP: 🟢 Synced (GR# 5678)                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Run #2 — 2026-03-28 — Line B                               │
│ Product: Finished Good B     Total: 300 cases               │
│ Status: ✅ COMPLETED                                        │
│ SAP: 🔴 Failed — "Connection timeout"  [Retry]             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Run #3 — 2026-03-28 — Line C                               │
│ Product: Manual Product      Total: 200 cases               │
│ Status: ✅ COMPLETED                                        │
│ SAP: ⚪ N/A (no SAP order linked)                           │
└─────────────────────────────────────────────────────────────┘
```

**React component example:**

```jsx
function SAPSyncBadge({ run }) {
    const { sap_sync_status, sap_sync_error, sap_receipt_doc_entry } = run;

    if (sap_sync_status === "NOT_APPLICABLE") {
        return null; // or <Badge color="grey">N/A</Badge>
    }

    if (sap_sync_status === "SUCCESS") {
        return (
            <Badge color="green">
                SAP Synced (GR# {sap_receipt_doc_entry})
            </Badge>
        );
    }

    if (sap_sync_status === "FAILED") {
        return (
            <div className="flex items-center gap-2">
                <Badge color="red">SAP Failed</Badge>
                <Tooltip content={sap_sync_error}>
                    <InfoIcon />
                </Tooltip>
                <RetryButton runId={run.id} />
            </div>
        );
    }

    // PENDING
    return <Badge color="yellow">SAP Syncing...</Badge>;
}
```

### 3. Retry Button Component

```jsx
function RetryButton({ runId }) {
    const [loading, setLoading] = useState(false);

    async function handleRetry() {
        setLoading(true);
        try {
            const response = await api.post(
                `/api/production-execution/runs/${runId}/retry-sap-receipt/`
            );
            const run = response.data;
            if (run.sap_sync_status === "SUCCESS") {
                showSuccess(`SAP Receipt posted! GR# ${run.sap_receipt_doc_entry}`);
            } else {
                showError(run.sap_sync_error);
            }
            // Refresh the run data in parent component
            refreshRunData(runId);
        } catch (err) {
            showError(err.response?.data?.detail || "Retry failed");
        } finally {
            setLoading(false);
        }
    }

    return (
        <Button
            size="sm"
            variant="outline"
            color="red"
            onClick={handleRetry}
            loading={loading}
        >
            Retry SAP
        </Button>
    );
}
```

### 4. Run Detail Page — SAP Section

Add a dedicated SAP section on the run detail page for completed runs:

```jsx
function RunDetailSAPSection({ run }) {
    if (run.status !== "COMPLETED" || !run.sap_doc_entry) {
        return null;
    }

    return (
        <Card title="SAP Integration">
            <DescriptionList>
                <Item label="SAP Production Order">
                    DocEntry: {run.sap_doc_entry}
                </Item>
                <Item label="Goods Receipt Status">
                    <SAPSyncBadge run={run} />
                </Item>
                {run.sap_receipt_doc_entry && (
                    <Item label="GR Document Entry">
                        {run.sap_receipt_doc_entry}
                    </Item>
                )}
                {run.sap_sync_error && (
                    <Item label="Error">
                        <Text color="red">{run.sap_sync_error}</Text>
                    </Item>
                )}
            </DescriptionList>
        </Card>
    );
}
```

### 5. Run List — Filter by SAP Sync Status (optional enhancement)

The frontend can filter completed runs by their SAP sync status to help operators find runs that need attention:

```javascript
// Filter runs that failed SAP sync
const failedRuns = runs.filter(r => r.sap_sync_status === "FAILED");

// Show a notification badge on the dashboard
if (failedRuns.length > 0) {
    showNotification(`${failedRuns.length} run(s) need SAP retry`);
}
```

---

## Quantity Logic

The backend posts `total_production - rejected_qty` to SAP:

| Scenario | total_production | rejected_qty | Posted to SAP |
|----------|-----------------|--------------|---------------|
| Normal | 500 | 0 | 500 |
| With rejects | 500 | 10 | 490 |
| All rejected | 100 | 100 | 0 (skipped, status = NOT_APPLICABLE) |

The frontend does NOT need to calculate this — the backend handles it automatically.

---

## Error Handling Matrix

| Scenario | HTTP Status | `status` | `sap_sync_status` | Frontend Action |
|----------|-------------|----------|--------------------|-----------------|
| Run completed, SAP success | 200 | COMPLETED | SUCCESS | Show success |
| Run completed, SAP fails | 200 | COMPLETED | FAILED | Show warning + retry |
| Run completed, no SAP order | 200 | COMPLETED | NOT_APPLICABLE | No SAP badge |
| Run completed, net qty <= 0 | 200 | COMPLETED | NOT_APPLICABLE | No SAP badge |
| Validation error (active segments) | 400 | unchanged | unchanged | Show error |
| Retry succeeds | 200 | COMPLETED | SUCCESS | Update badge |
| Retry fails again | 200 | COMPLETED | FAILED | Keep retry button |

**Key point:** The complete endpoint always returns `200` even if SAP posting fails. The production run is marked `COMPLETED` regardless. SAP sync failures are non-blocking — they are tracked via `sap_sync_status` and can be retried.

---

## Complete API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/production-execution/runs/{id}/complete/` | Complete run + auto-post to SAP |
| `POST` | `/api/production-execution/runs/{id}/retry-sap-receipt/` | Retry failed SAP goods receipt |
| `GET` | `/api/production-execution/runs/` | List runs (includes SAP status) |
| `GET` | `/api/production-execution/runs/{id}/` | Run detail (includes SAP status) |

---

## TypeScript Interface

```typescript
interface ProductionRun {
    id: number;
    sap_doc_entry: number | null;
    run_number: number;
    date: string;
    line: number;
    line_name: string;
    product: string;
    rated_speed: string | null;
    labour_count: number;
    other_manpower_count: number;
    supervisor: string;
    operators: string;
    total_production: string;
    total_running_minutes: number;
    total_breakdown_time: number;
    rejected_qty: string;
    reworked_qty: string;

    // SAP Goods Receipt fields
    sap_receipt_doc_entry: number | null;
    sap_sync_status: "NOT_APPLICABLE" | "PENDING" | "SUCCESS" | "FAILED";
    sap_sync_error: string;

    status: "DRAFT" | "IN_PROGRESS" | "COMPLETED";
    created_by: number | null;
    created_at: string;
    updated_at: string;

    // Detail-only fields
    segments?: ProductionSegment[];
    breakdowns?: MachineBreakdown[];
    machine_ids?: number[];
}
```
