# APH Admin Guide

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi (§26–§27, §90–§95)

The admin console is a self-contained SPA served by the backend at
`/admin` (same origin as the API). Sign in with an administrator account.

## Dashboard (§26)

- **Totals**: drugs, products, verified products, pending reviews,
  manufacturers, countries, images, sources, failed imports.
- **Charts**: records per body system (EN+AR labels), verification-status
  distribution.
- **Recent imports**: file, status, rows, imported count.

## Modules

### Drugs (§27, §90)
List/search (EN/AR name, ATC) · filter by verification status · rich editor
(basic info, mechanism, overview) · **Save Draft** · verification actions
(Submit for Verification → Verify → Archive) · illegal transitions are
rejected by the workflow engine.

### Products (§7, §15)
Search brand/barcode/registration · detail view (ingredients, packages,
images, manufacturer, linked generic) · **Check Duplicates** (exact/possible/
potential — human decides; never auto-merged) · verify/submit for review.

### Systems & Classes (§4, §70)
All 18 systems with drug counts · drill into therapeutic groups →
pharmacological classes · manage hierarchy (settings.manage).

### Manufacturers & Sources (§24)
CRUD manufacturers; register sources with **type + license metadata**
(regulatory / official label / reference / manufacturer / imported).

### Imports (§55)
7-step wizard: Upload → Format → Column mapping (auto-suggested, editable) →
Preview & validation report → Duplicate report → Import (**into pending
review**) → Pharmacist review → Publish via the verification workflow.
Error reports export as CSV/JSON (§56); failed rows can be retried (§98).

### Review Queue (§93)
Pending products · pending drugs · needs-update records. Verify only against
appropriate authoritative sources; every transition writes a
`verification_records` entry with a JSON snapshot + audit log.

### Image Review (§91)
Pending images with product, source, uploader, date · Approve / Reject.

### Data Quality (§57)
Automated checks: missing generic name, missing strength, invalid dosage
form, missing manufacturer, duplicate product, missing source, unverified
source, missing Arabic/English translation, broken image, invalid barcode,
conflicting classification, expired verification. The score measures
**completeness only — NOT medical reliability**.

### Users & Roles (§28)
Assign the 7 roles (public_user, pharmacist_reviewer, data_manager,
image_reviewer, translator, administrator, super_administrator). Role changes
are audit-logged.

### Audit Logs (§29)
Filter by action / entity type / entity id. **Append-only** — nobody can
modify or delete entries through the API.

### Exports (§82)
Filtered CSV/JSON export (`data.export` permission) — large exports are
audit-logged. Unauthorized bulk extraction is impossible.

## Role cheat-sheet

| Role | Typical tasks |
|------|----------------|
| pharmacist_reviewer | verify drugs/products, approve images, review queues |
| data_manager | create/edit records, run imports, manage sources |
| image_reviewer | image queue |
| translator | EN/AR fields (machine translations must be marked & reviewed) |
| administrator | everything incl. users, settings, exports |
| super_administrator | full system control |

## Tips

- Everything created via import stays **pending review** until a pharmacist
  verifies it — that is by design (§19, §85).
- Use the DEMO badge/is_demo filter to keep development data out of reviews.
- Keep sources registered BEFORE attaching them to records — provenance is
  the backbone of trust (§24–§25).
