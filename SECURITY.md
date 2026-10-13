# APH Security Model

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
(§46–§47, §77)

## Authentication (§45)

- Email/password; passwords hashed with **PBKDF2-HMAC-SHA256** (390k
  iterations, per-hash random salt, constant-time comparison).
- **JWT** access tokens (12 h) + refresh tokens (14 d) with server-side jti
  records (`refresh_tokens`, revocable).
- Password reset: single-use, hashed, expiring tokens; the API never reveals
  account existence.
- Login failure counting on `users.failed_login_count`.
- Optional OAuth (Google/Apple) can be added behind the same session model —
  never required for basic access.

## Authorization — RBAC (§28)

7 roles × 17 granular permissions (`drug.read` … `settings.manage`).
Enforced by FastAPI dependencies (`require_permission`) — server-side, never
UI-only. Privilege escalation paths (public user → create drug, manage users,
verify records) return **403** and are covered by tests.

## Transport & secrets

- HTTPS everywhere in production (TLS termination at the reverse proxy).
- Secrets (`SECRET_KEY`, DB credentials, AI provider keys, storage keys) come
  from **environment variables** only (§80) — never committed, never logged,
  **never shipped in the Flutter client** (§46).
- CORS restricted by configuration.

## Input handling

- Pydantic validation on every request body/query.
- SQLAlchemy parameterized queries — SQL-injection tested (§77).
- XSS: the API returns JSON; the admin SPA escapes all interpolated values
  (`esc()` helper); no `dangerouslySetInnerHTML`-style sinks.
- Rate limiting per IP+route group (auth routes stricter).
- Error responses carry friendly codes/messages — **stack traces never leak**.

## File uploads & image security (§47)

- Only JPEG/PNG/WebP — verified by **magic bytes**, not by extension or
  client MIME (spoofed `fake.png` containing HTML is rejected).
- Size cap (8 MB default); reject executables/unknown types/oversized files.
- Sanitized, unguessable storage names (`uuid + sha256` prefix); original
  filenames are never trusted or served.
- Images land as `pending_verification` — an **image reviewer** approves
  before they become public record (§91).

## Audit (§29)

Append-only `audit_logs`: user, action, entity, previous/new value, timestamp,
IP. No API mutates or deletes audit rows; reading them requires `audit.read`.
Logged actions include: login, role changes, drug/product CRUD, verification
transitions, image approvals, import execution, large exports.

## Data & privacy (§64)

- Minimal personal data: account email/name, optional device sync metadata.
- Search analytics are **anonymous aggregates** (no user linkage) (§67).
- AI conversations are user-scoped and deletable/exportable per privacy policy.
- No unnecessary health data collection.

## Backup & recovery (§60)

Automated pg_dump backups with retention (`backend/scripts/backup_db.py`),
restore runbooks in [DEPLOYMENT.md](DEPLOYMENT.md). Secrets for backup
destinations live in the ops secret store.

## Security testing (§77)

`backend/tests/test_security.py` covers: unauthorized access, privilege
escalation, invalid tokens, malicious/spoofed uploads, SQL injection input,
error leakage, audit integrity, export auditing, admin endpoint protection.
Recommended additionally in staging: dependency scanning, TLS verification,
rate-limit probing, and periodic secret rotation.
