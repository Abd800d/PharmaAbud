# AbdulmajeedPharma (APH)

### Professional Pharmaceutical Drug Encyclopedia & Intelligent Drug Database
### موسوعة عبدالمجيد للأدوية

**© Dr. Abdulmajeed Abdullah Almakhedhi**

---

APH is a scalable pharmaceutical information platform — **drug encyclopedia +
product database + pharmaceutical search engine + verification workflow +
offline mobile app + AI assistant** — architected around one principle:

> «100,000+ verified pharmaceutical products, continuously expandable,
> source-linked, searchable, bilingual, secure, offline-capable, and
> professionally maintained.»

## Platform components

| Component | Tech | Location |
|-----------|------|----------|
| Backend API | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic | `backend/` |
| Database | PostgreSQL (prod) · SQLite (dev/tests) | `backend/alembic/` |
| Admin Dashboard | Self-contained SPA served at `/admin` | `admin/` |
| Mobile App | Flutter (Android-first, PWA-ready) | `mobile/` |
| Offline Layer | SQLite (FTS, sync queue, favorites) | `mobile/lib/core/database/` |
| Sample Import Data | CSV / JSON / XLSX — clearly marked DEMO | `sample_data/` |

## Quick start (backend + admin)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# development database (SQLite) + demo seed
DATABASE_URL="sqlite:///./aph_dev.db" .venv/bin/python -m app.db.init_db

# run API + admin dashboard
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API docs (OpenAPI): http://localhost:8000/docs
- Admin dashboard: http://localhost:8000/admin
  (dev login after seeding: `admin@aphdemo.com` / `ChangeMe!123` — **change immediately**)

Run the test suite (85 tests):

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

## Mobile app

**Download the APK (ready-to-install release build):**

> **https://github.com/Abd800d/PharmaAbud/releases/download/apk-v1.0.0/app-release.apk**
> — Release [apk-v1.0.0](https://github.com/Abd800d/PharmaAbud/releases/tag/apk-v1.0.0) · ~63 MB · Android (arm64) · built by CI on every `mobile/**` change.

```bash
cd mobile
flutter create --platforms=android . && flutter pub get
flutter test
flutter run --dart-define=APH_API_BASE=http://10.0.2.2:8000/api/v1
```

The cloud build (`Build Android APK` workflow) produces the APK on every
relevant push and publishes it to the GitHub Release above — no Flutter
installation required. The same file is also available as the
`aph-mobile-release-apk` Actions artifact on each run.

## What is implemented

- **18 medical systems** (EN + AR) → Therapeutic Groups → Pharmacological
  Classes → Drugs → Products → Packages → Images
- **Strict drug/product separation** — scientific data lives on the drug,
  commercial data on the product; combination products supported
- **Comprehensive monographs** — mechanism, PK, indications, dosing,
  contraindications, warnings, interactions, pregnancy/lactation, monitoring,
  overdose… all bilingual, dose rows never invented
- **Search engine** — exact/prefix/partial/fuzzy ranking, Arabic
  normalization, typo tolerance, barcode lookup, filters, suggestions
- **Import engine** — CSV/XLSX/JSON/XML/ZIP/SQLite, column mapping,
  normalization (strengths, forms, routes), duplicate detection
  (exact/possible/potential — never auto-merged), error reports (CSV/JSON)
- **Verification workflow** — draft → imported → pending review → verified …
  with versioned history and audit trail
- **Source registry + field-level source links** (§24–§25)
- **RBAC** — 7 roles, granular permissions; JWT auth; password hashing
- **Audit logs** — append-only, every sensitive action
- **Offline-first mobile** — SQLite dataset modes (Essential / Selected
  Systems / Full), sync engine with conflict detection and retry queue
- **Barcode scanning** (EAN/GTIN/UPC) + **OCR-ready pipeline** (confidence
  estimates, manual correction)
- **APH AI Assistant** — RAG over the verified knowledge base with citations,
  safety layer and medical disclaimer; extractive provider runs fully offline
  and cannot fabricate facts it did not retrieve
- **Admin dashboard** — stats/charts, drug & product editors, taxonomy,
  imports wizard, review queues, image review, data-quality checks, users &
  roles, audit logs, exports (audited)
- **Data quality** — completeness checks (explicitly NOT a medical score)

## Data integrity principles (§85–§87)

- **No fabricated pharmaceutical data.** Seed/demo records are marked
  `is_demo = true`, carry DEMO labels in the UI, and sit in
  `imported_pending_review` — never `verified`.
- Unavailable doses read exactly: **"Not available / Requires verified source"**.
- Only import data you have rights to (§84). Track source/license metadata.
- The target is **100,000+ verified products**, not 100,000+ unverified rows.

## Documentation

| Document | Topic |
|----------|-------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture & data flow |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | PostgreSQL schema reference |
| [API.md](API.md) | REST API reference |
| [IMPORT_GUIDE.md](IMPORT_GUIDE.md) | Bulk import pipeline |
| [OFFLINE_SYNC.md](OFFLINE_SYNC.md) | Offline datasets & synchronization |
| [SEARCH.md](SEARCH.md) | Search engine & ranking |
| [AI_RAG.md](AI_RAG.md) | AI assistant / RAG architecture |
| [SECURITY.md](SECURITY.md) | Security model |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment |
| [TESTING.md](TESTING.md) | Test strategy |
| [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | Admin dashboard guide |
| [DATA_VERIFICATION.md](DATA_VERIFICATION.md) | Verification workflow |

## Medical disclaimer

APH is intended for educational and professional reference purposes. It does
not replace official prescribing information, clinical judgment, or advice
from a qualified healthcare professional. Always verify current official
product information before making clinical decisions.

## Support

- WhatsApp: 781733795
- Email: 7a8b1d@gmail.com

---

© Dr. Abdulmajeed Abdullah Almakhedhi — All rights reserved.
