# 6. Learning, trust and confidence

BoloDB's accuracy is not static — it improves with use, per database, because
of a simple loop: **every answer you confirm becomes an example the AI sees
next time.** This chapter covers the knowledge base, the confidence badge,
and the trust level.

## The knowledge base (`backend/app/knowledge.py`)

A small local SQLite file (`~/.bolodb/knowledge.db`, path set in
`backend/app/config.py`) with two tables, both keyed by a database
fingerprint (`db_id`, derived in `backend/app/database.py` → `db_id_for()` —
so knowledge for one connected database never leaks into another):

1. **`verified`** — question, SQL, restatement of every answer you confirmed.
   Written by `KnowledgeBase.add_verified()` (near-duplicate questions are
   skipped — similarity > 0.92).
2. **`glossary`** — your confirmed business terms:
   term → plain meaning → SQL hint. Written during onboarding
   (`set_glossary()`).

### How verified answers are found again

When a new question arrives, `retrieve_similar()` scores it against every
stored verified question:

```
similarity = 0.6 × word-overlap (Jaccard) + 0.4 × character-sequence ratio
```

(code: `_similarity()`). The top 3 above a 0.25 threshold are injected into
the AI prompt as worked examples (`_examples_block()` in
`backend/app/llm.py`) — few-shot examples of *your own verified SQL* are the
strongest accuracy signal the system has.

## The confidence badge (`backend/app/schema_link.py` → `compute_confidence()`)

The High/Medium/Low badge is computed from **observable signals** — never
from asking the AI how confident it feels. The exact rules:

| Situation | Badge | Reason shown |
|---|---|---|
| The query failed to run | **Low** | "the generated query did not run - please rephrase" |
| Best verified match ≥ 0.78 similarity | **High** | "closely matches an answer you verified before" |
| Best verified match ≥ 0.50 | **Medium** | "similar to an answer you verified before" |
| No match, query returned zero rows | **Low** | "no matching rows - the question may not match your data" |
| No match, query returned rows | **Medium** | "new question - please confirm it is right" |

Note what this implies: **the only way to see High confidence is to verify
answers.** That's intentional — high confidence is earned from your
confirmations, not claimed.

## The trust level (Supervised → Assisted → Trusted)

A per-database summary of how much verified knowledge exists — computed in
`KnowledgeBase.trust_level()` and mirrored in the frontend
(`frontend/src/lib/data.ts` → `trustFor()`):

| Verified answers | Level | Product behaviour |
|---|---|---|
| 0–2 | **Supervised** | Every answer waits for your confirmation while it learns. |
| 3–6 | **Assisted** | Confident answers shown; novel ones get a second look. |
| 7+ | **Trusted** | Answers shown directly; reasoning on tap. |

Displayed as the pill in the chat top bar
(`frontend/src/lib/components/ui/TrustPill.svelte`) and the meter in
onboarding (`TrustMeter.svelte`).

## The feedback flow, end to end

1. You click **"Yes, correct"** on an answer card
   (`frontend/src/lib/components/AnswerCard.svelte`).
2. `POST /api/feedback` → `backend/app/controllers/query.py` →
   `feedback()`.
3. The verdict is logged (`backend/app/logbook.py` — an append-only JSONL
   file per session in `~/.bolodb/sessions/`, useful for auditing what was
   asked and answered).
4. If the verdict is "correct", the pair is stored via `add_verified()` and
   the new trust level is returned to the UI.
5. Clicking **"Something's wrong"** logs the verdict + reason (wrong numbers /
   wrong filter / not what I meant …) without storing the answer.

## Explain — trust without reading SQL

For any query, `POST /api/explain` (`backend/app/llm.py` → `explain_sql()`)
returns 2–4 plain-English sentences describing what the SQL actually does —
which data it looks at, how it filters and groups, how it's ordered. It's the
"reverse translation" that lets a non-technical user audit an answer without
learning SQL.

## Where each artifact lives on disk

| Artifact | Location | Written by |
|---|---|---|
| Settings (model, API key — key encrypted at rest) | `~/.bolodb/config.json` + `~/.bolodb/.secret` | `backend/app/config.py` |
| Verified answers + glossary | `~/.bolodb/knowledge.db` | `backend/app/knowledge.py` |
| Session query/feedback log | `~/.bolodb/sessions/session-*.jsonl` | `backend/app/logbook.py` |
| Per-user query history | MongoDB (Docker volume) | `backend/app/mongodatabase.py` |
