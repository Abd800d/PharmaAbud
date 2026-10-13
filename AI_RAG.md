# APH AI Assistant — RAG Architecture

**AbdulmajeedPharma (APH)** — © Dr. Abdulmajeed Abdullah Almakhedhi
(§41–§43) · Implementation: `backend/app/services/rag.py`

## Purpose

Help users understand information **already present in the verified APH
knowledge base and properly linked sources** — e.g. mechanism of action,
adverse effects, dosage forms, comparing two drugs. The assistant is a
reference aid, not a prescriber.

## Pipeline (§41)

```
User Question
  ↓
Intent Detection          (mechanism | indications | dosage | interactions |
                           pregnancy | compare | products | …)
  ↓
APH Database Retrieval    (drugs/products via the search engine; monograph
                           sections: overview, mechanism, dosages, safety…)
  ↓
Verified Source Retrieval (DrugSource / ProductSource / ContentSource links)
  ↓
Context Construction      (bounded, section-filtered, verification-labelled)
  ↓
AI Response               (extractive provider — or optional LLM)
  ↓
Citations                 (ONLY sources actually retrieved)
  ↓
Safety/Quality Layer      (disclaimer, unavailable-messaging, grounded flag)
```

## Providers

| Provider | Config `AI_PROVIDER` | Behaviour |
|----------|----------------------|-----------|
| **extractive** (default) | `extractive` | Composes answers strictly from retrieved rows. Fully offline. **Cannot fabricate facts it did not retrieve.** |
| openai-compatible | `openai_compatible` | Optional LLM (`AI_OPENAI_BASE_URL`, `AI_OPENAI_API_KEY`, `AI_OPENAI_MODEL`). Receives the same grounded context; temperature 0; wrapped by the same safety layer. Keys live **only** in server env — never in the Flutter client (§46). |

## Safety rules (§42) — enforced in code

1. Prefer **verified** APH data; retrieved sections carry verification status.
2. **Cite sources** — citations recorded per message (`ai_citations`).
3. Distinguish source facts (retrieved text) from generated explanation.
4. **Never invent pharmaceutical facts** — empty retrieval yields exactly:
   *"The requested information could not be verified in the APH database."*
5. **Never fabricate dosage recommendations** — demo/unverified dose rows say
   *"Not available / Requires verified source"* verbatim.
6. Never pretend to be a doctor/pharmacist.
7. Always attach the **medical disclaimer** (EN/AR).
8. Encourage consultation of official product information for clinical decisions.

`grounded: true/false` in the API response tells the client whether any fact
was actually retrieved.

## Citations (§43)

Each response lists: source name · relevant section · URL where available ·
last-verified date where available. Citations are written to `ai_citations`
and are only produced for sources the retriever actually loaded — the
generator cannot cite anything else.

## Storage

`ai_conversations` → `ai_messages` → `ai_citations` (see DATABASE_SCHEMA.md).
Conversations are tied to user/device; the privacy policy covers retention and
deletion (§64).

## Extending

- New intents: extend `INTENT_KEYWORDS` / `INTENT_SECTIONS`.
- New providers: implement `generate(question, intent, entities, language)`
  returning `(answer_en, answer_ar, grounded)` — the safety wrapper and
  citation recording stay provider-independent.
- Retrieval improvements (rerankers, embeddings) slot in behind
  `retrieve_entities()` without changing the API contract.

## Testing

`backend/tests/test_sync_ai.py`: grounded answers with citations, unavailable
questions not fabricated, Arabic interface, dosage questions never invented,
citations only from retrieved sources, conversation persistence.
