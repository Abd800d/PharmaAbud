# APH Testing Strategy

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi (§74–§78)

## Test suites

| Suite | Location | Runs |
|-------|----------|------|
| Backend unit/integration (79 tests, 8 files) | `backend/tests/` | `pytest tests/ -q` |
| Flutter model/sync tests | `mobile/test/` | `flutter test` |
| Load generation (100k+ synthetic) | `backend/scripts/generate_synthetic.py` | manual / perf job |

## Backend coverage map (§74)

| Area | Tests |
|------|-------|
| Auth & sessions | `test_auth_rbac.py` — register/login/refresh/reset, bad tokens |
| RBAC | privilege escalation blocked (403s), role assignment, permission lists |
| Drugs & monographs | `test_drugs.py` — detail sections, demo flags, dose integrity |
| Verification workflow | illegal transitions rejected, history/versioning |
| Taxonomy | all **18 systems** present with groups/classes and demo drugs |
| Search (§75) | exact generic/brand, Arabic, prefix, typo/fuzzy, barcode, filters, combination products, no-result suggestions, typed generic-vs-product |
| Import (§19–§22) | CSV/JSON/XLSX/XML/ZIP parsing, column mapping, normalization (`500 mg`≡`500MG`≡`0.5 g`), duplicates (in-file + DB), error export, PG-dump guidance, retry |
| Sync (§32–§33) | incremental pull, push, **conflict detection**, device state, favorites ops |
| AI/RAG (§41–§43) | grounded answers, citations-only-retrieved, unavailable ≠ fabricated, Arabic, dosage never invented, conversation persistence |
| Security (§77) | unauth access, escalation, malicious/spoofed uploads, SQLi input, error leakage, audit integrity, export auditing |
| Ops | health, OpenAPI availability, admin dashboard stats, quality score |

## Synthetic scale testing (§74)

```bash
cd backend
python scripts/generate_synthetic.py --drugs 100000 --products 100000
```

Records are **SYNTH-prefixed, is_demo=true, NON-PRODUCTION** — they exist only
to measure search/import/sync performance and can never be mistaken for real
pharmaceutical data.

### Measured results (2026-10-13 — 100,031 drugs + 100,031 products, SQLite)

Generation: 200,000 synthetic rows in **74 s**. Search latency (median of 5,
limit 25; SQLite LIKE backend — PostgreSQL trigram indexes are faster):

| Query type | Median | p95 | Result quality |
|------------|--------|-----|----------------|
| Exact generic | 189 ms | 237 ms | 1 hit, `exact_generic` |
| Exact brand | 223 ms | 251 ms | 1 hit, `exact_brand` |
| Prefix (`SYNTH-Demolo`) | 235 ms | 283 ms | ranked prefix matches |
| Partial token (`zumab`) | 165 ms | 203 ms | partial matches |
| Typo / fuzzy (`SYNTH-Demoprl-…`) | 391 ms | 428 ms | target found via fuzzy rescue |
| Arabic (`سينث 54321`) | 188 ms | 237 ms | Arabic-normalized matches |
| Barcode (`SYNTH100042424`) | 206 ms | 241 ms | 1 hit, `barcode` |
| No result | 212 ms | 226 ms | 0 hits + suggestions |
| Suggestions | 38 ms | — | — |
| Deep pagination (offset 200) | 251 ms | — | stable |

Conclusions: ranking stays **precise at 200k+ records** (exact queries return
exactly the target with the correct match type); the two-pass retrieval
(precise `%token%` → typo-rescue only when empty) keeps candidate sets small;
production PostgreSQL adds trigram/tsvector/BRIN indexes (migration 0001) for
sub-100 ms targets at 500k+.

Record actual numbers during your own runs — do not trade correctness for
benchmarks (§78).

## Manual test checklists

### Offline (§76)
1. Airplane mode → banner appears.
2. Search downloaded data → open drug → open product → favorites → recents.
3. Add favorite offline → reconnect → sync → verify server state.
4. Force a conflict (edit on two devices) → conflict surfaced, no silent overwrite.
5. Kill network mid-sync → failed queue → retry succeeds.

### RTL / localization (§3, §54)
1. Switch to Arabic → full RTL layout, Arabic typography, RTL navigation.
2. Search `أموكسيسيلين` and mixed-language queries.
3. Check long Arabic strings, badges, bottom navigation, dialogs.
4. Screen reader labels, touch targets ≥ 44dp, high-contrast theme.

### Security (§77)
1. Call admin endpoints with a public token → 403.
2. Upload `evil.exe`, spoofed `fake.png` (HTML content) → 422.
3. Invalid/expired JWT → 401; SQLi strings → 200 with safe results.
4. Verify audit entries for every sensitive action; confirm no mutation route.

### Performance (§78)
1. Startup < ~2 s on a mid-range device (local dataset).
2. Local search results feel instant; server search debounced (300 ms).
3. Long lists lazy-load; images load via thumbnails.
4. Measure during the synthetic runs; record actual numbers — do not trade
   correctness for benchmarks.

## CI

`backend-ci.yml` runs the full backend suite on **SQLite and PostgreSQL**
(with `alembic upgrade head`). `build-apk.yml` runs `flutter test` before
building the APK.
