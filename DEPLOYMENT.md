# APH Production Deployment

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
(§79–§80)

## Environments

| Env | DATABASE_URL | Notes |
|-----|--------------|-------|
| development | `sqlite:///./aph_dev.db` or local Postgres | demo seed allowed |
| staging | staging Postgres | production-like, synthetic + demo data |
| production | managed Postgres | **no demo data**, `python -m app.db.init_db --no-demo` |

**Never hard-code secrets. Never reuse production secrets in development (§80).**

## Backend (FastAPI)

```bash
# 1. install
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. configure environment
export DATABASE_URL="postgresql+psycopg2://aph:SECRET@db-host:5432/aph"
export SECRET_KEY="$(openssl rand -hex 32)"
export ENVIRONMENT=production
export CORS_ORIGINS='["https://admin.your-domain.com"]'
export STORAGE_BACKEND=s3            # or local
export STORAGE_S3_BUCKET=aph-images
export AI_PROVIDER=extractive        # or openai_compatible + key

# 3. migrate + seed baseline (roles/permissions/systems)
alembic upgrade head
python -m app.db.init_db --no-demo

# 4. run (systemd / supervisor / container)
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app.main:app
```

Reverse proxy (nginx/Caddy) terminates **HTTPS**, forwards to uvicorn, and
serves `/admin` (same origin) and `/api/v1`. Configure client body size for
imports (e.g. 64 MB) and image uploads.

## PostgreSQL

- Managed instance (RDS/Cloud SQL/Neon…) with automated backups + PITR.
- `alembic upgrade head` on every deploy (migrations are versioned — §100).
- Connection pooling via SQLAlchemy (`pool_size`, `max_overflow`) +
  PgBouncer recommended at >4 app instances.
- Extensions created by migration 0001: `pg_trgm`.

## Object storage (images, §16)

S3-compatible bucket (or local volume for small installs):

- Private bucket + app-mediated access, or CDN with signed URLs.
- Layout: `products/<kind>/<uuid>_<sha>.ext` + `thumb_…` (CDN-compatible).
- Lifecycle: keep originals; backups cross-region.

## Background jobs

Large imports and scheduled backups run as workers/queues (Redis + RQ/Celery
or systemd timers calling `backend/scripts/`). The API enqueues; the worker
reports back to `imports` rows — admins can leave the page while processing
continues (§97).

## Backup & recovery (§60)

```bash
python scripts/backup_db.py --out /backups --retain 14
```

- Daily full pg_dump (custom format) + WAL/PITR where available.
- Retention policy enforced by the script (default 14).
- **Restore drill** (runbook): `pg_restore --clean -d aph /backups/aph-pg-*.dump`
  into staging; verify counts + smoke tests.
- Export API (`/admin/export`) for authorized JSON/CSV extracts (audited).

## Monitoring & logging

- Structured logs (app/security/audit/import/sync/ai streams) → stdout →
  your log stack (CloudWatch/Loki/ELK).
- Health endpoint `GET /health` for load balancer checks.
- Error reporting (Sentry or equivalent) on the server — never show reports
  to end users (§72).
- Alert on: 5xx rate, sync conflict spikes, import failures, backup failures.

## Mobile release (§79)

```bash
cd mobile
flutter create --platforms=android .
flutter build appbundle --release --dart-define=APH_API_BASE=https://api.your-domain.com/api/v1
```

- Sign with your upload keystore (stored in the CI secret store, never in Git).
- CI builds: `.github/workflows/build-apk.yml` (APK artifact) — extend with a
  signed AAB job for Play upload.
- PWA/web build (`flutter build web`) is supported by the same codebase.

## CI/CD

- `backend-ci.yml` — pytest on SQLite + PostgreSQL, then `alembic upgrade head`.
- `build-apk.yml` — analyze + test + build APK artifact.
- Recommended pipeline: lint → tests → build image → migrate → deploy staging →
  smoke → promote production.

## Environment variables (full list)

See `backend/app/core/config.py`: `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`,
`CORS_ORIGINS`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `RATE_LIMIT_*`,
`STORAGE_BACKEND`, `STORAGE_S3_*`, `IMAGE_MAX_BYTES`, `IMPORT_UPLOAD_ROOT`,
`AI_PROVIDER`, `AI_OPENAI_*`, `SYNC_PAGE_SIZE`, `LOG_LEVEL`.
