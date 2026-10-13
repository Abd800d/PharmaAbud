# APH REST API

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
Base URL: `/api/v1` · Interactive docs: `/docs` · ReDoc: `/redoc` · Spec: `/openapi.json`

## Conventions (§37, §96)

- **Auth**: `Authorization: Bearer <access_token>` (JWT). Public read endpoints
  work without a token; mutations require permissions (RBAC).
- **Errors**: `{"error": {"code", "message", "details"}}` — friendly messages,
  never stack traces. Codes: `not_found`, `unauthorized`, `forbidden`,
  `validation_error`, `conflict`, `rate_limited`, `server_error`.
- **Pagination**: `?page=&limit=` → `{items, total, page, limit, has_more}`
  (cursor pagination supported on sync endpoints). Limits: max 100.
- **Search syntax**: free text (EN/AR), barcodes, ATC codes; filters via query
  params. See [SEARCH.md](SEARCH.md).
- **Rate limiting**: per IP+route group (120/min default; 20/min for auth).
- **Versioning**: URL versioning (`/api/v1`). Additive changes only within a version.

## Auth — `/auth`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | — | create account (role: public_user) |
| POST | `/auth/login` | — | → `{access_token, refresh_token, expires_in}` |
| POST | `/auth/refresh` | — | rotate tokens |
| GET | `/auth/me` | ✓ | current user + roles + permissions |
| POST | `/auth/password-reset/request` | — | always 200 (no account enumeration) |
| POST | `/auth/password-reset/confirm` | — | token + new password |

Example:

```bash
curl -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@aphdemo.com","password":"ChangeMe!123"}'
```

## Drugs — `/drugs`

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/drugs` | — | list/filter (q, system_id, verification_status, page, limit, sort) |
| POST | `/drugs` | drug.create | create (status: draft) |
| GET | `/drugs/{id}` | — | full monograph (19 sections + sources) |
| PATCH | `/drugs/{id}` | drug.edit | update (bumps record_version, audited) |
| DELETE | `/drugs/{id}` | drug.delete | archive |
| PUT | `/drugs/{id}/synonyms` | drug.edit | replace synonyms |
| POST | `/drugs/{id}/dosages` | drug.edit | add dosage row (never invented — pass verified source text or "Not available / Requires verified source") |
| GET | `/drugs/{id}/products` | — | **Equivalent Products** (same active ingredient) |
| GET | `/drugs/{id}/alternatives` | — | **Therapeutic Alternatives** (different ingredients; not substitution advice) |
| POST | `/drugs/{id}/verify` | drug.verify | status transition `{new_status, notes}` |
| GET | `/drugs/{id}/verification-history` | — | versioned review history |

## Products — `/products`

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/products` | — | list/filter (q, drug_id, dosage_form, manufacturer_id, …) |
| POST | `/products` | product.create | create with ingredients[] |
| GET | `/products/{id}` | — | detail: ingredients, packages, images, sources, linked drug |
| PATCH | `/products/{id}` | product.edit | update (audited) |
| GET | `/products/{id}/duplicates` | product.edit | exact/possible/potential duplicates (never auto-merged) |
| POST | `/products/{id}/packages` | product.edit | add package |
| POST | `/products/{id}/images` | image.upload | multipart upload (JPEG/PNG/WebP only, magic-byte validated) |
| POST | `/products/{id}/verify` | product.verify | verification transition |

## Taxonomy & catalog

| Method | Path | Description |
|--------|------|-------------|
| GET | `/systems` | 18 body systems + drug counts |
| GET | `/systems/{id}/groups` | therapeutic groups → pharmacological classes |
| GET/POST | `/therapeutic-groups`, `/pharmacological-classes` | manage hierarchy (settings.manage) |
| GET/POST | `/dosage-forms`, `/routes`, `/countries` | normalized taxonomies |
| GET/POST | `/manufacturers` | manufacturers |
| GET/POST | `/sources` | source registry (source.manage) |

## Search — `/search`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search` | `q, kinds, system_id, therapeutic_group_id, pharmacological_class_id, dosage_form, route, manufacturer_id, country_id, verification_status, limit, offset` |
| GET | `/search/suggest` | instant suggestions (prefix) |
| POST | `/search/barcode` | barcode → product (unknown barcodes return empty — never invented) |
| POST | `/search/ocr?text=` | OCR text → candidates + matches + confidence estimates |

Response: `{query, total, items[{kind,id,name_en,name_ar,subtitle,match_type,score,verification_status,is_demo,extra}], took_ms, suggestions}`.

## Imports — `/imports` (import.create / import.approve)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/imports` | import history |
| POST | `/imports/upload` | multipart upload → validation preview + suggested column mapping + duplicates + errors |
| POST | `/imports/{id}/execute-file` | commit (`commit=true`) → records enter **pending review** |
| GET | `/imports/{id}/errors` | error rows |
| GET | `/imports/{id}/errors/export?format=csv\|json` | export error report (§56) |
| POST | `/imports/{id}/retry-failed` | re-process failed rows (§98) |

## Sync — `/sync` (§32–§33)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sync/pull` | `{device_id, entity_type, since, system_ids, limit}` → `{items, has_more, server_version, deleted_ids, server_time}` |
| POST | `/sync/push` | `{device_id, changes[{entity_type, entity_id, operation, payload, local_version, base_version}]}` → `{accepted, conflicts, failed, results}` — conflicts when server version > base_version |
| GET | `/sync/status` | per-device sync state |

## AI — `/ai` (§41–§43)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ai/ask` | `{question, language, conversation_id?, device_id?}` → `{answer, citations[], disclaimer, provider, intent, retrieved_entities, grounded}` — citations only from actually-retrieved sources |
| GET | `/ai/conversations` | conversation list + disclaimer |

## Admin — `/admin` (RBAC-gated)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/admin/dashboard` | drug.read+ | totals, charts (by system, verification status), recent imports |
| GET | `/admin/queues/review` | drug.verify+ | pharmacist review queues (§93) |
| GET | `/admin/quality` | product.edit+ | completeness report (NOT a medical score) |
| GET | `/admin/search-analytics` | settings.manage | anonymous aggregates only (§67) |
| GET | `/admin/export?entity=&format=` | data.export | CSV/JSON export — **audit-logged** (§82) |
| POST | `/admin/backup` | settings.manage | request backup (§60) |

## Users / Audit / Requests

| Method | Path | Permission |
|--------|------|------------|
| GET | `/users` | user.manage |
| GET | `/users/roles` | user.manage |
| PUT | `/users/{id}/roles` | user.manage (audited) |
| POST | `/drug-requests` | authenticated (§69) |
| GET | `/drug-requests` | drug.edit |
| GET | `/audit-logs?action=&entity_type=&entity_id=` | audit.read (append-only) |

## Images review — `/images` (§91)

`GET /images/review-queue` (image.approve) · `POST /images/{id}/approve` · `POST /images/{id}/reject`

## Ops

`GET /health` → `{status, app, version, environment}`.
