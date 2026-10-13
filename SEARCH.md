# APH Search Engine

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
Implementation: `backend/app/services/search.py` (§9–§10, §75, §83)

## Goals

Fast, typo-tolerant, bilingual pharmaceutical search that always
**distinguishes generic drugs from commercial products**, works offline on
downloaded data, and scales to 500k+ products.

## Indexed fields

Generic name (EN/AR) · scientific name · synonyms · active ingredients ·
brand names (EN/AR) · manufacturer · therapeutic & pharmacological classes ·
ATC code · barcode · GTIN · registration number.

## Ranking (§9)

| # | Match type | Score | Example |
|---|-----------|------|---------|
| — | Barcode / identifier | 110 | `6281100000011` |
| 1 | Exact generic | 100 | `amoxicillin` |
| 2 | Exact active ingredient | 90 | `clavulanate` on a combination product |
| 3 | Exact brand | 85 | `DemoBrand` |
| 4 | Exact Arabic | 80 | `أموكسيسيلين` |
| 5 | Synonym | 70 | registered synonym |
| 6 | Prefix | 60 | `amox` |
| 7 | Partial | 40 | `cillin` inside a name |
| 8 | Fuzzy (typo) | ~20–30 | `amoxcillin`, `amoxilin` |

Long natural-language questions score each token as well as the full string,
so "What is the mechanism of action of enalapril?" still returns Enalapril as
an **exact_generic** hit.

## Typo tolerance

SQL candidate retrieval uses informative tokens (stop-word filtered,
length-ordered) with `%token%` and `token[:4]%` fallbacks; deterministic
fuzzy re-ranking (`difflib`, threshold 0.72) handles:

- `amox` → Amoxicillin (prefix)
- `amoxcillin` / `amoxilin` / `amoxicilin` → Amoxicillin (fuzzy)
- `أموكس` → أموكسيسيلين (Arabic prefix)

When nothing matches, `suggestions` lists near-misses (did-you-mean) and the
UI offers spelling guidance + "Request New Drug" (§68–§69). Ambiguous
misspellings are never mapped to unsafe guesses.

## Arabic normalization (§22)

`normalize_arabic()`: strips harakat/tatweel; unifies alef variants
(أ إ آ ٱ → ا); ى→ي, ة→ه, ؤ→و, ئ→ي; NFKC; punctuation/whitespace collapse.
Applied to queries AND indexed text, so `أموكسيسيلين` ≡ `اموكسيسيلين`.
The raw original values are always preserved alongside normalized forms.

## Strength / taxonomy normalization

`500 mg` ≡ `500MG` ≡ `0.5 g` → canonical `500 mg` (original preserved).
Dosage forms (`Tabs`→`tablet`, `قرص`→`tablet`) and routes (`PO`→`oral`) map to
the normalized taxonomy used for filtering.

## Filters (§10)

Body system · therapeutic group · pharmacological class · dosage form ·
route · manufacturer · country · strength · verification status —
combinable with free text, applied in SQL before re-ranking.

## Results

Every hit is typed: `kind: "drug"` (Generic Drug) or `kind: "product"`
(Commercial Product), with `match_type`, `score`, `verification_status` and
`is_demo` so the UI can badge DEMO and unverified records.

## Performance (§48, §83)

1. **Candidate retrieval** — indexed SQL (btree/trigram), capped (400).
2. **Re-ranking** — deterministic Python scoring.
3. **Pagination** — server-side; never load 100k rows into a screen.

PostgreSQL adds `pg_trgm` GIN + tsvector GIN + BRIN (see migration 0001).
The API contract is engine-agnostic: OpenSearch/Elasticsearch can replace the
internal retrieval later without client changes (§49).

## Offline search (§66)

The Flutter client searches the downloaded SQLite set via indexed LIKE
(+ FTS5 when available) over the same fields (names, synonyms, ingredients,
manufacturer), ranked simply and clearly labelled as local results.

## Search analytics (§67)

`search_term_stats` aggregates terms/hits/zero-results **without user ids**.
Admins see "most searched" and "zero-result terms" (misspellings to fix);
individual users' queries are never exposed.

## Test matrix (§75)

Exact generic · exact brand · Arabic · English · synonym · partial · typo ·
fuzzy · barcode · manufacturer · combination product · strength · dosage
form · no result · large result set — covered in
`backend/tests/test_search.py`.
