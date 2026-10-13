# APH Data Verification Workflow

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi (§23, §59, §85, §93)

## Principle (§85)

> The target is **100,000+ verified pharmaceutical products** — not 100,000+
> unverified records. Every record should have traceable provenance whenever
> possible. Data integrity beats database size.

## Statuses (§23)

| Status | Meaning |
|--------|---------|
| `draft` | being authored in the admin editor |
| `imported` | raw import staging |
| `imported_pending_review` | created by an import — awaiting data-manager review |
| `pending_verification` | submitted to a pharmacist reviewer |
| `verified` | reviewed against appropriate authoritative source(s) |
| `needs_update` | verification expired / source changed / flagged |
| `rejected` | fails review (wrong, unsourceable, duplicate) |
| `archived` | retired from active use (history preserved) |

## Workflow

```
Imported → Pending Review → Pharmacist Review → Verified → Published
   │              │                │
   └── Rejected   └── Needs Update ┘
```

Transitions are enforced server-side (`backend/app/services/verification.py`)
— e.g. `draft → verified` directly is rejected with the allowed set listed.
Every transition writes:

1. a **`verification_records`** row — previous/new status, reviewer, review
   date, version, notes, JSON snapshot of the record at review time;
2. an **`audit_logs`** entry — who/what/when/IP.

Major records carry `record_version`, `created_by/updated_by`,
`verified_at/verified_by`, `last_source_update` (§59) — the backbone of
synchronization and auditability.

## Review dashboards (§93)

The admin **Review Queue** shows: pending products, pending drugs,
needs-update records, potential duplicates, missing sources, conflicting
data. Reviewers compare **current data / source data / previous version**
(the snapshot in `verification_records`).

## Evidence rules (§24–§25)

- Attach sources to records (`drug_sources` / `product_sources`) and — where
  possible — to individual sections (`content_sources`: dose → Source A,
  pregnancy → Source B…).
- Sources carry **type + license + dates**; authority is not uniform —
  a regulatory label outranks a random reference for labeling content.
  A search-engine result is never automatically authoritative.
- **Do not invent doses.** Unavailable dose rows read exactly:
  *"Not available / Requires verified source"*.
- **Pregnancy**: preserve the source's classification terminology; never
  invent old FDA A–X categories.
- **Off-label** indications are flagged `is_off_label`.
- **Therapeutic alternatives** (different ingredients) are clearly separated
  from **equivalent products** (same ingredient) and never presented as
  substitution recommendations (§11).

## DEMO data (§86–§87)

All seed/sample records are `is_demo = true`, show a DEMO badge and an
explicit warning banner, and sit in `imported_pending_review`. They exercise
the platform; they are **not** verified pharmaceutical information.

## Translation workflow (§58, §92)

`translations` rows track per-field EN↔AR status:
`original | human_reviewed | machine_translated | needs_review | missing`.
Machine translations are marked and must be human-reviewed before being
treated as verified content. Original source text is never overwritten.

## Expiry & re-verification

Records verified long ago (or whose source updated) flip to `needs_update`;
the data-quality dashboard surfaces expired verification. Re-verification
follows the same transition rules and appends to history — versions are never
lost.

## Drug request pipeline (§69)

User **Request New Drug** → request queue → data manager research →
pharmacist review → verification → publish. Tracked in `drug_requests`
(requester, date, name, reason, status, reviewer, source).
