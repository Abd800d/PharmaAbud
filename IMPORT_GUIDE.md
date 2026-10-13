# APH Import Guide

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
Implementation: `backend/app/services/import_engine.py` (§19–§22, §55–§56, §97–§98)

## Principle

> **Never blindly publish imported data.** Every imported row enters
> `imported_pending_review` and must pass pharmacist review + verification.

## Pipeline

```
UPLOAD → FILE VALIDATION → COLUMN MAPPING → DATA NORMALIZATION
→ VALIDATION → DUPLICATE DETECTION → CATEGORY MAPPING
→ SOURCE ATTACHMENT → IMPORT → PENDING REVIEW → PHARMACIST REVIEW
→ VERIFICATION → PUBLISH
```

## Supported formats

| Format | Notes |
|--------|-------|
| CSV | UTF-8 (BOM tolerated), header row required |
| XLSX | first sheet; header row required |
| JSON | array of objects, or `{items: [...]}` |
| XML | repeated elements with child fields |
| ZIP | containing any of the above (+ image files, §99) |
| SQLite | imports the largest table |
| PostgreSQL dump | **not parsed in-process** — load via `pg_restore` into staging, then use the API import source |
| API imports | POST rows through the API pipeline |

## Column mapping (§20)

The engine auto-maps aliases (`GenericName`, `generic_name_en`,
`الاسم العلمي` …) to canonical fields:

`GenericName(EN/AR) · BrandName(EN/AR) · ActiveIngredient · Strength ·
StrengthValue · StrengthUnit · DosageForm · Route · Manufacturer · Country ·
MarketingCountry · BodySystem · TherapeuticGroup · PharmacologicalClass ·
Mechanism · Indications · Contraindications · Warnings · Precautions ·
SideEffects · Interactions · FoodInteractions · Dosage · PediatricDosage ·
GeriatricDosage · RenalAdjustment · HepaticAdjustment · Pregnancy ·
Lactation · Barcode · RegistrationNumber · ImageURL · SourceURL ·
VerificationStatus`

Custom mapping: the upload response returns `suggested_mapping` — override any
column before executing the import.

## Normalization (§22)

- **Strengths**: `500 mg` / `500MG` / `0.5 g` → value+unit+canonical mg;
  original preserved on `import_rows.raw_data`.
- **Dosage forms**: `Tabs`/`قرص`/`Tab` → `tablet` (taxonomy slug).
- **Routes**: `PO`/`فموي` → `oral`.
- **Countries**: `KSA`/`السعودية` → `SA`.
- **Names**: Unicode NFKC + Arabic orthographic normalization for indexing.

## Duplicate detection (§21)

| Level | Rule | Action |
|-------|------|--------|
| **Exact** | same barcode / registration number (in DB or earlier row in the file) | row skipped as `duplicate_exact` — never merged |
| **Possible** | same brand + strength + form + manufacturer | flagged for human review |
| **Potential** | same brand (+ strength or manufacturer) | flagged for human review |

Uncertain records are **never automatically merged**; a human review interface
decides (also available per-product: `GET /products/{id}/duplicates`).

## Error reports (§56)

Every failed row records: row number · field · value · error · suggested
correction · status. Export as CSV or JSON
(`GET /imports/{id}/errors/export?format=csv|json`).

## Large imports (§97–§98)

- Upload → preview validates the first 500 rows instantly.
- Execution processes the batch transactionally per row; one bad row never
  kills the batch (row-level error capture).
- `POST /imports/{id}/retry-failed` re-processes failed rows without
  restarting the import.
- Files > 64 MB: split or use the background-worker deployment pattern
  (upload → queue → worker → report; see DEPLOYMENT.md).

## Source attachment & licensing (§24, §84)

Attach a `source_id` to every import (the source registry records name, URL,
type, dates and **license/usage information**). Only import data you have the
rights to use — public-domain, properly licensed, official where permitted,
or your own. Never scrape in violation of terms.

## Image import (§99)

Map images to product records via barcode / product ID / SKU / registration
number / brand+strength+manufacturer. Ambiguous matches are queued for human
review — filename matching is never trusted blindly.

## Sample data

`sample_data/` contains clearly-marked **DEMO / DEVELOPMENT DATA** (CSV,
JSON, XLSX) including intentional duplicates and invalid rows to exercise the
whole pipeline.
