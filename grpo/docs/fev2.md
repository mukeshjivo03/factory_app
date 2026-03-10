# Frontend Changes Required — GRPO Attachment Fix v2

## What Changed (Backend)

The SAP error `200039` ("Select OK in Approve Column After Adding Attachment") was occurring when PATCHing an existing GRPO document to link an attachment.

### Fix Applied

**Post-creation attachment uploads** (`POST /api/v1/grpo/<id>/attachments/` and retry) now use a smarter approach:

1. **If the GRPO already has an AttachmentEntry** (created with attachments at posting time):
   - New files are added as **lines to the existing Attachments2 entry** in SAP
   - The GRPO document itself is **NOT modified** — no approval error
2. **If the GRPO has no AttachmentEntry** (posted without attachments):
   - Falls back to the old flow: upload → PATCH document (may still trigger approval error)

---

## Frontend Changes Needed

### No changes required if you already implemented fev1.md

If the frontend already:
- Sends attachments during GRPO posting (via `FormData` with `data` + `attachments` fields)
- Uses the `POST /api/v1/grpo/post/` endpoint with multipart support

Then **no frontend changes are needed**. The backend handles everything transparently.

---

### Changes needed ONLY if post-creation attachment upload is used

If the frontend uses `POST /api/v1/grpo/<posting_id>/attachments/` to upload attachments **after** GRPO is already posted, here's what to know:

#### 1. Retry Button — No Code Change Needed

The retry endpoint (`POST /api/v1/grpo/<posting_id>/attachments/<attachment_id>/retry/`) works the same way. The backend now automatically detects existing attachment entries and uses the safe path. No frontend changes needed.

#### 2. Post-Creation Upload — No Code Change Needed

The `POST /api/v1/grpo/<posting_id>/attachments/` endpoint works the same way. The backend now handles it internally. No request/response format changes.

#### 3. (Optional) Improve UX for the "no existing attachment" case

If a GRPO was posted **without** any attachments, and the user later tries to add one via `POST /api/v1/grpo/<posting_id>/attachments/`, SAP may still reject it with the approval error. The backend cannot avoid this for documents that were created without an `AttachmentEntry`.

**Recommended UI hint:**

```javascript
// When showing the "Add Attachment" option on GRPO detail page,
// consider showing a warning if the GRPO was posted without attachments:

if (grpoDetail.attachments.length === 0) {
  showInfo(
    'This GRPO was posted without attachments. ' +
    'Adding attachments after posting may fail due to SAP approval rules. ' +
    'For best results, attach files during GRPO posting.'
  );
}
```

---

## API Behavior Summary (No Format Changes)

| Endpoint | Behavior Change |
|----------|----------------|
| `POST /api/v1/grpo/post/` | No change. Attachments at creation time still work as before. |
| `POST /api/v1/grpo/<id>/attachments/` | Backend now adds to existing Attachments2 entry when possible. Same request/response format. |
| `POST /api/v1/grpo/<id>/attachments/<id>/retry/` | Same improvement. Same request/response format. |
| `GET /api/v1/grpo/<id>/attachments/` | No change. |
| `DELETE /api/v1/grpo/<id>/attachments/<id>/` | No change. |

---

## Response Format — No Changes

The attachment response format remains identical:

```json
{
  "id": 1,
  "original_filename": "invoice.pdf",
  "sap_attachment_status": "LINKED",
  "sap_absolute_entry": 789,
  "sap_error_message": null,
  "uploaded_at": "2026-03-10T12:00:00Z",
  "uploaded_by": "username"
}
```

Status values remain the same: `PENDING`, `UPLOADED`, `LINKED`, `FAILED`.

---

## Quick Summary

| Question | Answer |
|----------|--------|
| Do I need to change API calls? | **No** |
| Do I need to change request format? | **No** |
| Do I need to change response handling? | **No** |
| Should I add a UX warning? | **Optional** — only for GRPOs posted without attachments |
| Best practice going forward? | Always attach files during GRPO posting, not after |
