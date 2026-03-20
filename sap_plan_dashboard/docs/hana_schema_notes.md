# SAP HANA Schema Notes — Plan Dashboard

> **Purpose:** Documents the verified actual column names for every SAP B1 HANA table
> used by `sap_plan_dashboard`. Verified by direct inspection against the live HANA instance
> at `103.89.45.192` / schema `TEST_OIL_15122025`.
>
> **Last verified:** 2026-03-16

---

## Bug History

When the app was first written, three column names were wrong (based on SAP B1 documentation
rather than the actual HANA table schema). All three caused a `dbapi.ProgrammingError`
(column not found), which surfaced as HTTP 502 with:

```json
{"detail": "SAP data error: Failed to retrieve plan dashboard data from SAP. Invalid query."}
```

| # | File | Column used | Actual column | Table |
|---|------|------------|---------------|-------|
| 1 | `hana_reader.py` | `T0."ItemName"` | `T0."ProdName"` | `OWOR` |
| 2 | `hana_reader.py` | `T0."Dscription"` (intermediate fix) | `T0."ProdName"` | `OWOR` |
| 3 | `hana_reader.py` | `T1."Warehouse"` | `T1."wareHouse"` | `WOR1` |
| 4 | `hana_reader.py` | `T1."ItemType" = 'I'` | `T1."ItemType" = 4` | `WOR1` |
| 5 | GROUP BY clause | `T0."Dscription"` | `T0."ProdName"` | `OWOR` |

All 5 were fixed. All 41 unit tests pass after the fix.

---

## Verified Column Reference

### `OWOR` — Production Orders

Inspected via `SYS.TABLE_COLUMNS` WHERE `TABLE_NAME = 'OWOR'`.

| Column | Type | Used as |
|--------|------|---------|
| `DocEntry` | INTEGER | Primary key — used in all joins |
| `DocNum` | INTEGER | User-visible order number |
| `ItemCode` | NVARCHAR | Finished good item code (SKU) |
| **`ProdName`** | NVARCHAR | **Finished good name/description** ← use this, NOT `ItemName` or `Dscription` |
| `PlannedQty` | DECIMAL | Total planned qty |
| `CmpltQty` | DECIMAL | Already completed qty |
| `Status` | NVARCHAR | `'P'` = Planned, `'R'` = Released, `'L'` = Closed, `'C'` = Cancelled |
| `DueDate` | TIMESTAMP | Target completion date |
| `PostDate` | TIMESTAMP | Document posting date |
| `Priority` | SMALLINT | Order priority |
| `Warehouse` | NVARCHAR | Default warehouse code for the order |

> **Note:** OWOR does NOT have `ItemName` or `Dscription`. Both cause ProgrammingError.
> The SAP B1 Service Layer exposes this as `ProductDescription`, but the HANA table column is `ProdName`.

---

### `WOR1` — Production Order Components (BOM Explosion)

Inspected via `SYS.TABLE_COLUMNS` WHERE `TABLE_NAME = 'WOR1'`.

| Column | Type | Used as |
|--------|------|---------|
| `DocEntry` | INTEGER | FK → `OWOR.DocEntry` |
| `LineNum` | INTEGER | Line sequence number within the order |
| `ItemCode` | NVARCHAR | Component item code |
| `ItemName` | NVARCHAR | Component item name (exists in WOR1, not just OITM) |
| `PlannedQty` | DECIMAL | Total planned qty of this component for the order |
| `IssuedQty` | DECIMAL | Already issued to production floor |
| **`wareHouse`** | NVARCHAR | **Source warehouse** ← lowercase 'w', uppercase 'H' — case-sensitive in HANA |
| `BaseQty` | DECIMAL | Qty per unit of parent (from BOM master) |
| `UomEntry` | INTEGER | FK to `OUOM` table (integer key) |
| **`UomCode`** | NVARCHAR | **Unit of measure string** (e.g. `'LTR'`, `'KG'`, `'PC'`) |
| **`ItemType`** | INTEGER | **`4` = Item, `290` = Resource** ← integer, NOT char `'I'` |
| `IssueType` | NVARCHAR | `'M'` = Manual, `'B'` = Backflush |

> **Critical:** `wareHouse` is camelCase. `"Warehouse"` (capital W, lowercase h) does NOT exist
> in WOR1. HANA double-quoted identifiers are case-sensitive.

> **Critical:** `ItemType` values are integers: `4` = Items, `290` = Resources.
> Using `= 'I'` causes a type error (comparing INTEGER to NVARCHAR).
> Correct filter: `T1."ItemType" = 4`

---

### `OITM` — Item Master Data

| Column | Type | Used as |
|--------|------|---------|
| `ItemCode` | NVARCHAR | Primary key |
| `ItemName` | NVARCHAR | Item description (correct column name) |
| `OnHand` | DECIMAL | Total on-hand quantity |
| `IsCommited` | DECIMAL | Committed / reserved for open orders |
| `OnOrder` | DECIMAL | On purchase orders (incoming) |
| `InvntItem` | NVARCHAR | `'Y'` = inventory tracked, `'N'` = non-inventory |
| `LeadTime` | INTEGER | Vendor lead time in days |
| `CardCode` | NVARCHAR | Default vendor code |

> All OITM column names were correct from the start.

---

## SQL Column Name Quick Reference

Use this table when writing new HANA queries:

```
OWOR item name:            "ProdName"          (NOT ItemName, NOT Dscription)
WOR1 warehouse:            "wareHouse"         (camelCase, case-sensitive)
WOR1 unit of measure:      "UomCode"           (string code, e.g. 'LTR')
WOR1 item type filter:      ItemType = 4       (integer, not 'I')
OITM net available:        OnHand - IsCommited
```

---

## Test Results After Fix

```
Ran 41 tests in 18.983s
OK
```

Queries verified against `TEST_OIL_15122025` schema:

| Query | Rows returned |
|-------|--------------|
| Summary (OWOR + WOR1 + OITM) | 117 orders |
| Details (BOM explosion) | 548 component lines |

---

## Adding New Queries

If you write new queries touching these tables:

1. Always wrap column names in double quotes: `T0."DocEntry"`
2. For WOR1 warehouse: use `T1."wareHouse"` — not `T1."Warehouse"`
3. For OWOR description: use `T0."ProdName"` — not `T0."ItemName"` or `T0."Dscription"`
4. For item type filter on WOR1: `T1."ItemType" = 4` — not `= 'I'`
5. Test every new column name with a direct `SYS.TABLE_COLUMNS` inspect before deploying
