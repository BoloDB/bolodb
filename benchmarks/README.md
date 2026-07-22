# Benchmarks

Measurement for the question the whole product hangs on: **when a user asks
something, does the AI get shown the right tables — and does it produce the
right SQL?** Until these numbers exist, linking quality is anecdote.

## The Spider benchmark

[Spider](https://github.com/taoyds/spider) (Yale, taoyds/spider) is the
standard academic benchmark for cross-domain text-to-SQL: ~1000 dev-set
questions over 20 SQLite databases, each with the gold (correct) SQL written
by experts. We replay those questions through BoloDB's own pipeline.

### Getting the dataset

Download the Spider dataset (`spider.zip`) from the link on
https://yale-lily.github.io/spider (Google Drive) or the Hugging Face mirror
(`xlangai/spider`), and unzip it. You need this layout:

```
spider/
├── dev.json                    # the questions + gold SQL
└── database/
    ├── concert_singer/concert_singer.sqlite
    ├── pets_1/pets_1.sqlite
    └── ...
```

The dataset is a few hundred MB and is NOT checked into this repository.

### Measuring linking recall (free, offline, no API key)

```bash
pip install -r backend/requirements.txt
python -m benchmarks.spider_eval --spider-dir /path/to/spider
```

For every question this runs BoloDB's real introspection
(`backend/app/database.py` → `get_schema`) and table selection
(`backend/app/schema_link.py` → `link_relevant_tables`) in **cold-start**
conditions (no glossary, no verified answers — the hardest case), then checks
whether every table the gold SQL uses was in the set we would have shown the
AI.

- **Linking recall** = fraction of questions where nothing was missed. A miss
  means the AI could not possibly have answered correctly.
- Every miss is written to `benchmarks/spider_report.jsonl` with the exact
  question, gold tables and what we sent instead — the debugging queue for
  improving the scoring weights.

### Measuring end-to-end execution accuracy (costs tokens)

```bash
OPENROUTER_API_KEY=your-key python -m benchmarks.spider_eval \
    --spider-dir /path/to/spider --generate --limit 100
```

Additionally generates SQL with the real OpenRouter model and compares the rows it
returns against the rows the gold SQL returns (order-insensitive). Use
`--limit` to control cost; `--model` to compare model tiers.

### Interpreting results

- Track **linking recall first** — it upper-bounds everything else.
- Run before and after any change to scoring weights
  (`schema_link.py`), budgets (`model_budget`) or prompt shape: the report
  makes regressions visible before customers see them.
- Spider databases are small (most fit inside the table budget entirely, where
  linking trivially succeeds); the interesting rows in the report are the
  bigger schemas. For production-scale signals on 100+ table databases, pair
  this with the audit trail below.

## The production audit trail

Real usage is logged so any wrong answer can be traced back to "what did the
AI actually see":

- Every `/api/query` response carries `tables_used` (final set, including
  schema-retry additions) and `attempts` (how many generation rounds the
  repair loop needed).
- Both are also written per query to the session log
  (`~/.bolodb/sessions/session-*.jsonl` — `backend/app/logbook.py`), next to
  the question, SQL, confidence and any error. High `attempts` counts or
  answers whose `tables_used` misses an obvious table are the production
  equivalent of a failed benchmark row.
