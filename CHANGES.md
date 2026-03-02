# Changes Branch vs Main — Detailed Changelog

**Branch:** `changes`
**Base:** `main`
**Date range:** 2026-02-18 to 2026-02-26
**Total commits:** 22 (including 3 merge commits)
**Files changed:** 32 (+648 lines, -75 lines)

---

## Table of Contents

1. [SAP HANA Connection: Migrate from pyodbc to hdbcli](#1-sap-hana-connection-migrate-from-pyodbc-to-hdbcli)
2. [Add JIVO_BEVERAGES Company Configuration](#2-add-jivo_beverages-company-configuration)
3. [Arrival Slip File Attachments](#3-arrival-slip-file-attachments)
4. [File Upload Size Limit Increased to 15 MB](#4-file-upload-size-limit-increased-to-15-mb)
5. [Arrival Slip "Send Back to Gate" Feature](#5-arrival-slip-send-back-to-gate-feature)
6. [Inspection Model Enhancements](#6-inspection-model-enhancements)
7. [Soft-Delete Recovery for MaterialType and QCParameterMaster](#7-soft-delete-recovery-for-materialtype-and-qcparametermaster)
8. [SAP PO Reader: Add Price/Rate and DocEntry Fields](#8-sap-po-reader-add-pricerate-and-docentry-fields)
9. [Vehicle Management Enhancements](#9-vehicle-management-enhancements)
10. [Gate Completion: Weighment Made Optional](#10-gate-completion-weighment-made-optional)
11. [Serializer Context Fixes (Request Propagation)](#11-serializer-context-fixes-request-propagation)
12. [Miscellaneous](#12-miscellaneous)

---

## 1. SAP HANA Connection: Migrate from pyodbc to hdbcli

**Commits:** `e9eec82`, `9885554`

The SAP HANA database connection driver was changed from `pyodbc` (ODBC-based) to `hdbcli` (SAP's native Python driver). This removes the dependency on the HDBODBC system driver and simplifies deployment.

### Files changed

| File | Change |
|------|--------|
| `sap_client/hana/connection.py` | Replaced `pyodbc.connect(...)` with `dbapi.connect(address=, port=, user=, password=)` |
| `sap_client/hana/po_reader.py` | `import pyodbc` → `from hdbcli import dbapi`; all `pyodbc.Error` / `pyodbc.ProgrammingError` → `dbapi.Error` / `dbapi.ProgrammingError` |
| `sap_client/hana/vendor_reader.py` | Same driver swap as above |
| `sap_client/hana/warehouse_reader.py` | Same driver swap as above |
| `requirement.txt` | Added `hdbcli` package |

### Before / After (connection.py)

```python
# BEFORE
import pyodbc
conn = pyodbc.connect(
    f"DRIVER={{HDBODBC}};SERVERNODE={host}:{port};UID={user};PWD={password}"
)

# AFTER
from hdbcli import dbapi
conn = dbapi.connect(address=host, port=port, user=user, password=password)
```

---

## 2. Add JIVO_BEVERAGES Company Configuration

**Commit:** `cf7547e`

A new company "JIVO_BEVERAGES" was registered across the SAP configuration layer.

### Files changed

| File | Change |
|------|--------|
| `config/settings.py` | Added `"JIVO_BEVERAGES": config('COMPANY_DB_JIVO_BEVERAGES')` to `COMPANY_DB` dict |
| `sap_client/registry.py` | Added full `JIVO_BEVERAGES` entry in `COMPANY_SAP_REGISTRY` with HANA and Service Layer connection config |

### Impact
- A new environment variable `COMPANY_DB_JIVO_BEVERAGES` is now required in `.env`.
- The new company can now use all SAP HANA/Service Layer integrations (PO lookup, vendor lookup, warehouse lookup).

---

## 3. Arrival Slip File Attachments

**Commits:** `18f5185`, `3b34580`, `51fe577`, `10f2db8`, `28eefc8`

A new attachment system was added to the Arrival Slip workflow. Gate operators can upload Certificate of Analysis (COA) and Certificate of Quantity (COQ) files when submitting an arrival slip.

### New model: `ArrivalSlipAttachment`

**File:** `quality_control/models/arrival_slip_attachment.py`

```python
class AttachmentType(models.TextChoices):
    CERTIFICATE_OF_ANALYSIS = "CERTIFICATE_OF_ANALYSIS"
    CERTIFICATE_OF_QUANTITY = "CERTIFICATE_OF_QUANTITY"

class ArrivalSlipAttachment(models.Model):
    arrival_slip = ForeignKey(MaterialArrivalSlip, related_name="attachments")
    file = FileField(upload_to="arrival_slip_attachments/")
    attachment_type = CharField(choices=AttachmentType.choices)
    uploaded_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("arrival_slip", "attachment_type")
```

### New serializer: `ArrivalSlipAttachmentSerializer`

**File:** `quality_control/serializers.py`

Returns `id`, `file`, `attachment_type`, `uploaded_at`.

### Changes to `ArrivalSlipSubmitAPI`

**File:** `quality_control/views.py`

- Added `MultiPartParser` and `FormParser` to accept file uploads.
- On submit, validates that:
  - If `has_certificate_of_analysis` is `true` on the slip, a `certificate_of_analysis` file must be uploaded (unless one already exists).
  - If `has_certificate_of_quantity` is `true` on the slip, a `certificate_of_quantity` file must be uploaded (unless one already exists).
- Uses `update_or_create` so resubmissions (after send-back) replace existing attachments of the same type.

### Serializer updates

- `MaterialArrivalSlipSerializer` now includes an `attachments` nested field.
- `RawMaterialInspectionSerializer` now includes `attachments` (sourced from `arrival_slip.attachments`) so inspections expose the slip's files.
- Inspection queryset updated to `prefetch_related("arrival_slip__attachments")`.

### API documentation updated

- `quality_control/api_doc.md`
- `quality_control/docs/api.md`
- `quality_control/docs/api_endpoints.md`

### Migration

- `0015_arrivalslipattachment.py` — Creates the new table.

---

## 4. File Upload Size Limit Increased to 15 MB

**Commit:** `acc4950`

**File:** `config/settings.py`

```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024  # 15 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024  # 15 MB
```

Previously used Django's default of 2.5 MB.

---

## 5. Arrival Slip "Send Back to Gate" Feature

**Commits:** `ac04df0`, `5e86485`

A new workflow action allows QC personnel to send a submitted arrival slip back to the gate for correction (e.g., wrong quantities, missing info). This is distinct from the existing rejection flow.

### New API endpoint

```
POST /api/v1/quality-control/arrival-slips/{slip_id}/send-back/
```

**Permission:** `can_send_back_arrival_slip` (granted to `qc_store`, `qc_chemist`, `qc_manager` groups)

**Request body:**
```json
{ "remarks": "Incorrect quantity entered" }
```

### Business rules

1. Only arrival slips with status `SUBMITTED` can be sent back.
2. If an inspection exists and is still in `DRAFT` status, it is **soft-deleted** (`is_active=False`, `is_locked=True`, `arrival_slip` set to `NULL` to free the OneToOne).
3. If the inspection has already been submitted to a chemist (beyond DRAFT), the send-back is blocked — the inspection rejection flow must be used instead.
4. The arrival slip is reset to `DRAFT` / `is_submitted=False` so the gate operator can edit and resubmit.
5. Vehicle entry status is set to `ARRIVAL_SLIP_REJECTED`.

### New model fields on `MaterialArrivalSlip`

| Field | Type | Description |
|-------|------|-------------|
| `sent_back_by` | `ForeignKey(User)` | User who sent the slip back |
| `sent_back_at` | `DateTimeField` | Timestamp of the send-back |

### New model method on `MaterialArrivalSlip`

```python
def send_back_to_gate(self, user, remarks=""):
```

### New model method on `RawMaterialInspection`

```python
def cancel_for_send_back(self, user, remarks=""):
    # Sets is_active=False, is_locked=True, arrival_slip=None
    # Also soft-deletes related parameter_results
```

### New permission class

```python
class CanSendBackArrivalSlip(BasePermission)
```

### New notification

**File:** `quality_control/signals.py`

When an arrival slip is sent back (`status=DRAFT` and `sent_back_by` is not null), a notification of type `ARRIVAL_SLIP_SENT_BACK` is sent to the `qc_store` group.

**File:** `notifications/models.py` — Added `ARRIVAL_SLIP_SENT_BACK` to `NotificationType`.

### Migrations

- `0017_add_send_back_fields_and_permission.py` — Adds `sent_back_by`, `sent_back_at` fields and `can_send_back_arrival_slip` permission.
- `0018_add_send_back_perm_to_groups.py` — Data migration granting the permission to `qc_store`, `qc_chemist`, and `qc_manager` groups.

---

## 6. Inspection Model Enhancements

**Commits:** `5028fa1`, `3e0634c`, `1248fbd`

### 6.1 New field: `internal_report_no`

**File:** `quality_control/models/raw_material_inspection.py`

```python
internal_report_no = models.CharField(max_length=100, blank=True)
```

A manually-filled field for QC staff to record their internal report number. Added to serializers, admin search fields, and admin fieldsets.

### 6.2 `internal_lot_no` now user-overridable

**File:** `quality_control/views.py` — `InspectionCreateUpdateAPI`

Previously, `internal_lot_no` was always auto-generated. Now the client can optionally provide it; the auto-generated value is used as a fallback:

```python
internal_lot_no = data.pop("internal_lot_no", None) or RawMaterialInspection.generate_lot_no()
```

`internal_lot_no` added to `RawMaterialInspectionCreateSerializer`.

### 6.3 Fields made optional

| Field | Old | New |
|-------|-----|-----|
| `purchase_order_no` | required | `blank=True` (optional) |
| `supplier_batch_lot_no` | required | `blank=True` (optional) |

Updated in both model and `RawMaterialInspectionCreateSerializer`.

### 6.4 `material_type_name` in inspection list

**File:** `quality_control/serializers.py` — `InspectionListItemSerializer`

New `get_material_type_name` method returning the material type's name. Queryset updated with `select_related("inspection__material_type")`.

### Migration

- `0016_make_po_lot_optional_add_internal_report_no.py` — Adds `internal_report_no`, makes `purchase_order_no` and `supplier_batch_lot_no` optional.

---

## 7. Soft-Delete Recovery for MaterialType and QCParameterMaster

**Commit:** `b1c1d2a`

**File:** `quality_control/views.py` — `MaterialTypeListCreateAPI.post()` and `QCParameterListCreateAPI.post()`

When creating a new MaterialType or QCParameterMaster, the API now checks if a soft-deleted record with the same `code` / `parameter_code` already exists. If found, it **reactivates** the existing record (sets `is_active=True`, updates fields) instead of creating a duplicate.

### Before

```python
material_type = MaterialType.objects.create(company=..., **data)
```

### After

```python
existing = MaterialType.objects.filter(company=..., code=..., is_active=False).first()
if existing:
    # Update fields and reactivate
    existing.is_active = True
    existing.save()
else:
    # Create new
    MaterialType.objects.create(...)
```

Same pattern applied to `QCParameterMaster` with `parameter_code` as the lookup key.

---

## 8. SAP PO Reader: Add Price/Rate and DocEntry Fields

**Commit:** `910e0ab`

### Files changed

| File | Change |
|------|--------|
| `sap_client/dtos.py` | Added `rate: float = 0.0` and `line_num: int = 0` to `POItemDTO`; added `doc_entry: int = 0` to `PODTO` |
| `sap_client/serializers.py` | Added `rate` (DecimalField), `line_num` (IntegerField) to `POItemSerializer`; added `doc_entry` (IntegerField) to `POSerializer` |
| `sap_client/hana/po_reader.py` | SQL query now selects `T1."Price"`, `T0."DocEntry"`, `T1."LineNum"`; transformation logic maps these to DTOs |

### SQL change

```sql
-- Added columns:
T1."Price"    AS rate,
T0."DocEntry" AS doc_entry,
T1."LineNum"  AS line_num
```

### Impact
- API consumers now receive `rate`, `line_num`, and `doc_entry` in PO responses.
- `rate` represents the unit price from SAP's Purchase Order line item.
- `doc_entry` is SAP's internal document entry number.
- `line_num` is the line number within the PO.

---

## 9. Vehicle Management Enhancements

**Commits:** `bd6d8cf`, `25f3b54`

### 9.1 Supplier details in VehicleEntrySerializer

**File:** `vehicle_management/serializers.py`

The `VehicleEntrySerializer.to_representation()` now includes a `suppliers` array:

```python
representation["suppliers"] = [
    {"supplier_code": po.supplier_code, "supplier_name": po.supplier_name}
    for po in instance.po_receipts.all()
]
```

### 9.2 Query optimization with `prefetch_related`

**File:** `vehicle_management/views.py`

Both `VehicleEntryListCreateAPI` and `VehicleEntryListByStatus` now add `.prefetch_related('po_receipts')` to avoid N+1 queries when serializing supplier data.

### 9.3 Transporter update (PUT) endpoint

**File:** `vehicle_management/views.py` — `TransporterDetailAPI`

Added `put()` method allowing updates to transporter details. Documentation updated in `vehicle_management/README.md`.

---

## 10. Gate Completion: Weighment Made Optional

**Commit:** `0051eab`

**File:** `raw_material_gatein/services/gate_completion.py`

The `complete_gate_entry()` function no longer requires a weighment record to exist. The validation check:

```python
if not hasattr(vehicle_entry, "weighment"):
    raise ValueError("Weighment not completed")
```

was removed. Gate entry can now be completed with only:
1. Security check submitted
2. At least one PO item exists
3. All PO items have completed QC (ACCEPTED or REJECTED)

---

## 11. Serializer Context Fixes (Request Propagation)

**Commits:** Multiple (across `ac04df0`, `28eefc8`, etc.)

**File:** `quality_control/views.py`

All views that instantiate `MaterialArrivalSlipSerializer` or `RawMaterialInspectionSerializer` now pass `context={'request': request}`. This ensures `FileField` URLs are rendered as absolute URLs (Django REST Framework uses the request to build the full URL).

### Affected views

- `ArrivalSlipListAPI`
- `ArrivalSlipCreateUpdateAPI`
- `ArrivalSlipDetailAPI`
- `ArrivalSlipSubmitAPI`
- `InspectionCreateUpdateAPI`
- `InspectionDetailAPI`
- `InspectionSubmitAPI`
- `InspectionApproveChemistAPI`
- `InspectionApproveQAMAPI`
- `InspectionRejectAPI`
- `InspectionAwaitingChemistAPI`
- `InspectionAwaitingQAMAPI`

---

## 12. Miscellaneous

### 12.1 CSRF trusted origins cleanup

**Commit:** `dcb169d`

**File:** `config/settings.py`

Removed hardcoded `CSRF_TRUSTED_ORIGINS` from settings (likely moved to environment variable).

### 12.2 Claude Code local settings

**File:** `.claude/settings.local.json`

Added Claude Code permission settings for local development (pip install commands, etc.). This is a development-only file.

---

## Summary of New API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/quality-control/arrival-slips/{id}/send-back/` | Send arrival slip back to gate for correction |
| `PUT` | `/api/v1/vehicle-management/transporters/{id}/` | Update transporter details |

## Summary of New Database Migrations

| Migration | Description |
|-----------|-------------|
| `0015_arrivalslipattachment` | New `ArrivalSlipAttachment` model |
| `0016_make_po_lot_optional_add_internal_report_no` | Add `internal_report_no`, make `purchase_order_no` and `supplier_batch_lot_no` optional |
| `0017_add_send_back_fields_and_permission` | Add `sent_back_by`, `sent_back_at` fields and `can_send_back_arrival_slip` permission |
| `0018_add_send_back_perm_to_groups` | Grant send-back permission to `qc_store`, `qc_chemist`, `qc_manager` groups |

<!-- ## New Environment Variables Required -->

| Variable | Description |
|----------|-------------|
| `COMPANY_DB_JIVO_BEVERAGES` | SAP database name for JIVO Beverages company |
