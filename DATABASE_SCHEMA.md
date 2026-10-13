# APH Database Schema

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
PostgreSQL (production) · 53 tables · migrations in `backend/alembic/versions/`

Design rules:
- UUID string primary keys (`users.id`, stable across environments).
- `created_at` / `updated_at` on major tables (indexed).
- `record_version`, `created_by`, `updated_by`, `verified_at`, `verified_by`
  on major records (§59) — enables sync + auditability.
- `is_demo` flag: DEMO/development data is always distinguishable (§87).
- `verification_status` enum string: draft | imported | imported_pending_review |
  pending_verification | verified | needs_update | rejected | archived (§23).
- Bilingual columns `*_en` / `*_ar` — Arabic is first-class (§58).

## Identity & RBAC (§28)

| Table | Purpose |
|-------|---------|
| `users` | accounts: email (unique), password_hash (PBKDF2), flags, reset token |
| `roles` | 7 system roles (public_user … super_administrator) |
| `permissions` | granular codes: `drug.read`, `drug.verify`, `import.approve`, … |
| `user_roles` | user ↔ role M:N |
| `role_permissions` | role ↔ permission M:N |
| `refresh_tokens` | revocable refresh tokens (jti) |

## Taxonomy (§4, §8)

| Table | Purpose |
|-------|---------|
| `body_systems` | the 18 primary systems (slug, EN/AR names, sort_order) |
| `therapeutic_groups` | group under a body system |
| `pharmacological_classes` | class under a therapeutic group |
| `drug_classifications` | drug ↔ class (+system/group) M:N, `is_primary` flag |
| `dosage_forms` | normalized form taxonomy (admin-extensible) |
| `routes` | administration routes |
| `countries` | ISO-coded countries |
| `manufacturers` | EN/AR names, country FK, search_text |

## Drug monograph (§6)

`drugs` core table: EN/AR generic names, scientific name, pronunciation,
class fields, ATC/CAS/formula/weight, overview/mechanism/PK (EN+AR),
absorption/distribution/metabolism/elimination, half_life,
`is_combination`, `search_text` / `search_text_ar` (denormalized index),
`verification_status`, `is_demo`, versioning columns.

Child tables (each with `drug_id` FK, EN/AR text, sort_order):

| Table | Section |
|-------|---------|
| `drug_synonyms` | synonyms (language-tagged, normalized_term) |
| `drug_indications` | incl. `is_off_label` (§6) |
| `drug_contraindications` | absolute/relative severity |
| `drug_warnings` | boxed/warning/notice severity |
| `drug_precautions` | precautions |
| `drug_side_effects` | frequency + `is_serious` |
| `drug_interactions` | interacting_agent + severity |
| `drug_food_interactions` | food interactions |
| `drug_dosages` | population (adult/pediatric/geriatric/renal/hepatic), indication, route, text, value/unit, frequency, max_dose, duration, `is_verified` |
| `drug_pregnancy` | text + `risk_label` + `risk_system` (source terminology preserved — never invented FDA A–X) + source FK |
| `drug_lactation` | milk transfer, infant considerations |
| `drug_monitoring` | monitoring parameters |
| `drug_administration` | administration instructions |
| `drug_overdose` | overdose information |
| `drug_alternatives` | therapeutic alternatives (different ingredients, §11) |

## Products (§7, §16)

| Table | Purpose |
|-------|---------|
| `drug_products` | brand EN/AR, strength(+value/unit), dosage_form, route, manufacturer FK, manufacturing/marketing countries, barcode, GTIN, registration_number, status |
| `product_ingredients` | one row per active ingredient (combinations = 2+) |
| `product_packages` | package size/description, per-package barcode/GTIN |
| `product_images` | storage_path, kind (front/back/side/blister/bottle/label/leaflet/other), type, size, dimensions, thumbnail, source, copyright, uploaded_by, verification_status |

## Sources & provenance (§24–§25, §58)

| Table | Purpose |
|-------|---------|
| `sources` | name, URL, source_type (regulatory/official_label/reference/manufacturer/imported/demo), publication/retrieved dates, license_info |
| `drug_sources` / `product_sources` | record-level links with `section` |
| `content_sources` | field-level links (entity_type/entity_id/section → source) |
| `translations` | per-field translation tracking; `machine_translated` status must be human-reviewed before trusted |

## Operations (§19, §29, §32, §67, §69)

| Table | Purpose |
|-------|---------|
| `imports` | import jobs: format, column_mapping JSON, row counts, status |
| `import_rows` | per-row raw/normalized JSON, status, duplicate kind, created entity |
| `import_errors` | row/field/value/error/suggested_correction/status (exportable) |
| `verification_records` | every status transition + JSON snapshot + reviewer (version history) |
| `audit_logs` | append-only: user, action, entity, previous/new value, timestamp, IP |
| `favorites` | user favorites (folder, sort) |
| `recent_searches` | per-user/device recent searches |
| `search_term_stats` | anonymous aggregates (hits, zero_results) — no per-user exposure |
| `sync_queue` | entity/operation/payload, retry_count, status, versions |
| `device_sync_state` | per device: watermark, server_version, dataset_mode, downloaded systems |
| `drug_requests` | "Request New Drug" workflow (§69) |

## AI (§41–§43)

| Table | Purpose |
|-------|---------|
| `ai_conversations` | conversation header (user/device/language) |
| `ai_messages` | user/assistant messages, provider, safety_note |
| `ai_citations` | ONLY sources actually retrieved: source, section, entity, quote |

## Search optimization (§83)

Every searchable entity carries denormalized `search_text` columns maintained
on write. The initial migration adds on PostgreSQL:
- `pg_trgm` GIN indexes on names and search_text (fuzzy/partial retrieval)
- `to_tsvector` GIN index for full-text
- BRIN indexes on `updated_at` (sync watermarks)
- btree indexes on barcode, registration_number, atc_code, verification_status

## Migrations (§100)

```bash
cd backend
alembic upgrade head          # apply
alembic revision --autogenerate -m "..."   # new migration (review before commit!)
```

Never modify production schema outside migrations.
