# APH Architecture

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi

## Logical architecture (§101)

```
             APH MOBILE
              Flutter
                 │
    ┌────────────┴────────────┐
    │                         │
 Local SQLite             Secure API (FastAPI)
 │                         │
 Offline Search                │
 Favorites                     │
 Sync Queue                    │
 │                         │
 └────────────┬────────────┘
              │
           Backend
              │
    ┌──────────┴──────────┐
    │                     │
 PostgreSQL           Object Storage
    │                     │
 Drug Database          Product Images
    │
 Search · Verification · Sources
    │
    └──────────┐
               │
              RAG
               │
        APH AI Assistant

 Admin Dashboard (SPA) ── Secure API
```

## Repository layout

```
PharmaAbud/
  backend/          FastAPI application (app/, alembic/, tests/, scripts/)
  admin/            Admin SPA (served by the backend at /admin)
  mobile/           Flutter application (Clean Architecture)
  sample_data/      Clearly-marked DEMO import datasets
  docs and guides   13 documents at the repository root
```

## Backend (API layer)

- **FastAPI** with versioned REST endpoints (`/api/v1/...`) and OpenAPI docs.
- **SQLAlchemy 2.0** ORM; **Alembic** migrations (never hand-edit production schema).
- **PostgreSQL** in production (pg_trgm + full-text + BRIN indexes);
  **SQLite** for development/tests — the search layer abstracts the difference.
- Services (business logic) are independent of HTTP:
  `search`, `import_engine`, `duplicates`, `normalization`, `verification`,
  `audit`, `storage`, `sync`, `rag`, `ocr`, `quality`.
- Cross-cutting: JWT auth + RBAC dependencies, rate limiting, structured
  logging (app/security/audit/import/sync/ai streams), friendly error model
  (no stack traces to clients).

### Request flow (example: search)

```
GET /api/v1/search?q=أموكس
 → rate limit → SQL candidate retrieval (indexed, tokenized)
 → Python re-ranking (exact > ingredient > brand > Arabic > synonym
   > prefix > partial > fuzzy) → filter/sort/paginate
 → aggregate (anonymous) search stats → JSON response
```

## Domain model

Strict separation (§5):

- **Drug** — the scientific/generic entity with the full monograph
  (mechanism, PK, indications, dosing, safety, pregnancy/lactation…).
- **Product** — a commercial product containing drug(s)/ingredient(s);
  brand, strength, form, manufacturer, countries, barcode/registration.
- **ProductPackage / ProductImage** — presentations and permanent images.

Taxonomy (§4): `BodySystem (18) → TherapeuticGroup → PharmacologicalClass →
Drug → Product → ProductPackage → ProductImage`, with a many-to-many
`DrugClassification` so drugs can span systems when scientifically justified.

Provenance (§24–§25): `Source` registry with type/license metadata;
`DrugSource` / `ProductSource` record-level links; `ContentSource`
field/section-level links.

## Mobile (presentation + domain + data)

- **Presentation**: feature screens + shared design-system widgets.
- **Domain**: typed models (`DrugModel`, `ProductModel`, `SearchHitModel`…).
- **Data**: `AphRepository` (REST) with **offline fallback** to SQLite;
  `SyncService` + on-device `sync_queue`; `AuthRepository`.
- State: `provider` (`AppState` for settings/connectivity/DI).
- Localization: full EN/AR tables; RTL from locale.

## Admin dashboard

Self-contained SPA (no build step) served by FastAPI at `/admin`, consuming
the same `/api/v1` endpoints as mobile: dashboard charts, drug/product
editors, taxonomy, import wizard, review queues, image review, data quality,
users/roles, audit logs, exports.

## Sync & offline (§30–§33)

See [OFFLINE_SYNC.md](OFFLINE_SYNC.md). Watermark-based incremental pull;
changes push through a queue with retry; conflicts (server version > client
base version) are surfaced, never overwritten blindly.

## AI / RAG (§41–§43)

See [AI_RAG.md](AI_RAG.md). Intent detection → retrieval from the verified
database → context construction → generation → citations → safety layer.
The default **extractive** provider composes answers strictly from retrieved
rows (offline, zero hallucination of unretrieved facts).

## Scalability (§48–§49)

- Server-side pagination everywhere; client-side lazy loading.
- Indexed retrieval + deterministic re-ranking keeps search fast at
  500k+ products; the client API contract is search-engine agnostic —
  PostgreSQL FTS/trigram today, OpenSearch/Elasticsearch later without
  client changes.
- Connection pooling, background-able import pipeline (upload → worker →
  report), CDN-compatible image storage layout.
- Synthetic load-test generator: `backend/scripts/generate_synthetic.py`
  (100k+ records, `SYNTH-` prefix, `is_demo=true`).

## Deployment topology (production)

```
[CDN] → [Reverse proxy / TLS] → [uvicorn/gunicorn × N]
                                  ├─ PostgreSQL (primary + replica)
                                  ├─ Object storage (S3-compatible)
                                  └─ Backup scheduler (pg_dump, retention)
```

See [DEPLOYMENT.md](DEPLOYMENT.md).
