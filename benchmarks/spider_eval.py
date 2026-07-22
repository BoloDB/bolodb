"""Spider benchmark for BoloDB's schema linking (and, optionally, SQL generation).

Spider (https://github.com/taoyds/spider) is the standard academic benchmark
for cross-domain text-to-SQL: ~1000 dev questions over 20 SQLite databases,
each with the gold (correct) SQL. This script replays those questions through
BoloDB's own pipeline pieces and measures:

1. LINKING RECALL (always, offline, free): for each question, did
   ``link_relevant_tables`` keep every table the gold SQL actually uses?
   A miss here means the AI could never have answered correctly — this is the
   number that tells us how often our table-picking fails before a customer
   ever sees it.
2. EXECUTION ACCURACY (optional, needs OPENROUTER_API_KEY, costs tokens): run the
   full generate→validate→execute pipeline and compare the result rows of the
   generated SQL against the gold SQL, order-insensitively.

Usage (see benchmarks/README.md for getting the dataset):

    python -m benchmarks.spider_eval --spider-dir /path/to/spider
    python -m benchmarks.spider_eval --spider-dir /path/to/spider --limit 100
    OPENROUTER_API_KEY=... python -m benchmarks.spider_eval --spider-dir /path/to/spider \
        --generate --model deepseek-v4-flash --limit 50

Outputs a summary to stdout and a JSONL report (one line per question) with
every miss, so failures can be inspected one by one.
"""

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Allow `python benchmarks/spider_eval.py` from the repo root as well as -m.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import DatabaseManager  # noqa: E402
from backend.app.llm import OpenRouterProvider, generate_sql  # noqa: E402
from backend.app.schema_link import (  # noqa: E402
    compact_schema,
    extract_table_names_from_prev_query,
    link_relevant_tables,
    model_budget,
)


def load_examples(spider_dir, split):
    path = Path(spider_dir) / split
    if not path.exists():
        sys.exit(f"error: {path} not found — see benchmarks/README.md")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rows_multiset(result):
    """Execution result rows as an order-insensitive multiset for comparison."""
    rows = result.get("rows", []) or []
    return Counter(tuple(str(v) for v in row.values()) for row in rows)


async def run_generation(provider, question, schema, tables, budget, db, db_id):
    schema_text = compact_schema(schema, tables, budget["samples"])
    gen = await generate_sql(provider, question, schema_text, "sqlite", [], [])
    result = db.execute(db_id, gen.get("sql", ""))
    return gen, result


def main():
    ap = argparse.ArgumentParser(description="Spider linking/accuracy benchmark")
    ap.add_argument(
        "--spider-dir",
        required=True,
        help="Directory containing dev.json and database/",
    )
    ap.add_argument(
        "--split",
        default="dev.json",
        help="Examples file inside spider-dir (default dev.json)",
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="Evaluate only the first N examples"
    )
    ap.add_argument(
        "--model",
        default="deepseek-v4-flash",
        help="Model whose linking budget (and generation) to use",
    )
    ap.add_argument(
        "--generate",
        action="store_true",
        help="Also run SQL generation + execution accuracy (needs OPENROUTER_API_KEY)",
    )
    ap.add_argument(
        "--out",
        default="benchmarks/spider_report.jsonl",
        help="Per-example JSONL report path",
    )
    args = ap.parse_args()

    examples = load_examples(args.spider_dir, args.split)
    if args.limit:
        examples = examples[: args.limit]

    provider = None
    if args.generate:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            sys.exit(
                "error: --generate needs the OPENROUTER_API_KEY environment variable"
            )
        provider = OpenRouterProvider(api_key=key, model=args.model)

    db = DatabaseManager(readonly=True)
    budget = model_budget("openrouter", args.model)

    n = 0
    linking_hits = 0
    parse_failed = 0
    exec_matches = 0
    exec_run = 0
    skipped = 0
    total_tables_sent = 0
    report = open(args.out, "w", encoding="utf-8")

    for ex in examples:
        db_id = ex["db_id"]
        question = ex["question"]
        gold_sql = ex["query"]

        sqlite_path = Path(args.spider_dir) / "database" / db_id / f"{db_id}.sqlite"
        if not sqlite_path.exists():
            skipped += 1
            continue
        if not db.connected(db_id):
            res = db.connect(db_id, f"sqlite:///{sqlite_path}")
            if not res.get("ok"):
                skipped += 1
                continue

        schema = db.get_schema(db_id)
        gold_tables = {
            t.lower() for t in extract_table_names_from_prev_query(gold_sql, "sqlite")
        }

        # If the gold SQL cannot be parsed (non-standard syntax, parser edge
        # case), skip recall for this question — an empty set would falsely
        # count as a linking hit since the empty set is a subset of any set.
        if not gold_tables and gold_sql.strip():
            parse_failed += 1
            record = {
                "db_id": db_id,
                "question": question,
                "gold_sql": gold_sql,
                "note": "gold SQL could not be parsed — linking skipped",
            }
            report.write(json.dumps(record, ensure_ascii=False) + "\n")
            continue

        # Cold-start linking: no glossary, no verified history, no conversation.
        tables = link_relevant_tables(
            question, schema, [], [], budget["max_tables"], set()
        )
        sent = {t.lower() for t in tables}
        hit = gold_tables <= sent

        n += 1
        linking_hits += hit
        total_tables_sent += len(tables)

        record = {
            "db_id": db_id,
            "question": question,
            "gold_sql": gold_sql,
            "gold_tables": sorted(gold_tables),
            "tables_sent": sorted(sent),
            "linking_hit": hit,
            "missed_tables": sorted(gold_tables - sent),
        }

        if provider is not None:
            gen, result = asyncio.run(
                run_generation(provider, question, schema, tables, budget, db, db_id)
            )
            gold_result = db.execute(db_id, gold_sql)
            ok = (
                "error" not in result
                and "error" not in gold_result
                and rows_multiset(result) == rows_multiset(gold_result)
            )
            exec_run += 1
            exec_matches += ok
            record.update(
                {
                    "generated_sql": gen.get("sql", ""),
                    "exec_match": ok,
                    "exec_error": result.get("error"),
                }
            )

        report.write(json.dumps(record, ensure_ascii=False) + "\n")

    report.close()

    if not n:
        sys.exit("error: no examples evaluated — check --spider-dir layout")
    recall_denom = n - parse_failed
    print(f"examples evaluated : {n} (skipped {skipped})")
    if recall_denom:
        print(
            f"linking recall     : {linking_hits}/{recall_denom} = {linking_hits / recall_denom:.1%}"
        )
    else:
        print("linking recall     : N/A (no parseable gold SQL)")
    if parse_failed:
        print(f"  ({parse_failed} questions skipped — unparseable gold SQL)")
    if recall_denom:
        print(
            f"avg tables sent    : {total_tables_sent / recall_denom:.1f} (budget {budget['max_tables']}+FK)"
        )
    if exec_run:
        print(
            f"execution accuracy : {exec_matches}/{exec_run} = {exec_matches / exec_run:.1%}"
        )
    print(f"per-example report : {args.out} (misses have non-empty missed_tables)")


if __name__ == "__main__":
    main()
