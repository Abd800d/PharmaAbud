# APH Offline & Synchronization

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
(§30–§33, §66, §76)

## Offline-first principle

The Flutter app is fully usable without connectivity for everything the user
has downloaded: search, drug monographs, products, systems, favorites,
recent searches and downloaded images. An amber banner shows offline status.

## Local database (SQLite)

Tables: `drugs`, `products`, `body_systems`, `drug_sections`, `favorites`,
`recent_searches`, `recent_drugs`, `sync_queue`, `sync_state` (+ FTS5 virtual
table when the SQLite build supports it). Indexed on EN/AR names, brand,
barcode, `updated_at` (§66). Schema: `mobile/lib/core/database/local_database.dart`.

## Dataset strategy (§31)

Never download millions of records to every phone. Configurable modes:

| Mode | Content |
|------|---------|
| **Essential** | core verified drugs (default) |
| **Selected Systems** | user picks body systems (`downloaded_systems` list) |
| **Full** | complete available offline set (device storage permitting) |
| **Delta updates** | only records changed since the last watermark |

Settings → Offline Dataset shows dataset size, downloaded records, last
updated / last sync and storage used.

## Sync architecture (§32)

```
Flutter  ⇄  Sync Engine (SyncService)  ⇄  REST /sync  ⇄  PostgreSQL
```

### Pull (incremental)

`POST /api/v1/sync/pull` with `{device_id, entity_type, since, system_ids, limit}`.
The server returns records with `updated_at > watermark` (paged, `has_more`),
plus `deleted_ids`. Each record carries `record_version` + `updated_at`.
The client stores rows transactionally and advances
`device_sync_state.last_synced_at`.

### Push (local changes)

Local modifications queue in the on-device **sync_queue** (§33):

`id · entity_type · entity_id · operation · payload · created_at ·
retry_count · status · last_error · server_version · local_version`

`POST /api/v1/sync/push` applies changes with **conflict detection**:

> If the server record's `record_version` > the client's `base_version`,
> the change is marked **CONFLICT** — newer server data is **never**
> overwritten blindly. The client surfaces the conflict for resolution.

### Reliability

- Retry with `retry_count` + `last_error`; failed items stay queued.
- Background sync where platform permissions allow (`syncInterval` in config).
- `GET /api/v1/sync/status` reflects per-device state
  (last_synced_at, dataset_mode, downloaded systems, status).
- Favorites sync as explicit `favorite_add` / `favorite_remove` operations.

## Conflict handling policy

1. Server-newer → CONFLICT (client decides: keep local as a queued edit or discard).
2. Both-edited content fields → surface a comparison (current/server/local).
3. Deletes vs edits → prefer edit; surface if ambiguous.
4. Every applied server change bumps `record_version` and writes an audit entry
   when performed through authenticated endpoints.

## Offline testing checklist (§76)

Internet disabled → search downloaded data → open drug → open product →
favorites → recent searches → image viewing → make local change → reconnect →
sync → conflict path → failed sync → retry. Covered by
`mobile/test/sync_queue_test.dart` + backend `tests/test_sync_ai.py`, and the
manual checklist in [TESTING.md](TESTING.md).
