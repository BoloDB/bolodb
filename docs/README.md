# BoloDB Documentation

Welcome! These docs explain **what BoloDB does, how it does it, and where in
the code each piece lives**. They are written so that:

- a **non-technical reader** can follow every chapter top-to-bottom and
  understand the product, and
- a **developer** (or a curious founder) can jump from any paragraph straight
  into the code, because every mechanism is annotated with the file — and
  usually the exact function — where it happens.

## How to read these docs

If you are new, read chapters 1 → 2 first. After that, each chapter stands on
its own. Code pointers look like this:

> `backend/app/llm.py` → `generate_sql()`

which means: open that file, find that function.

## Chapters

| # | Chapter | What it answers |
|---|---------|-----------------|
| 1 | [What is BoloDB?](01-what-is-bolodb.md) | The product in plain language. What happens when you connect a database and ask a question. |
| 2 | [How a question becomes an answer](02-how-a-question-becomes-an-answer.md) | The full pipeline, step by step, with the exact code location for every step. **The most important chapter.** |
| 3 | [The AI layer (OpenRouter)](03-the-ai-layer-openrouter.md) | Everything about the AI: what is sent to Google, which models we use, API keys, retries, errors, and how to add another AI vendor later. |
| 4 | [Schema linking — choosing tables](04-schema-linking.md) | How BoloDB decides which tables the AI gets to see, and why that makes answers cheaper *and* more accurate. |
| 5 | [Safety, validation and self-repair](05-safety-validation-and-self-repair.md) | The three safety nets: read-only enforcement, SQL validation before execution, and the automatic repair loop. |
| 6 | [Learning, trust and confidence](06-learning-trust-and-confidence.md) | How BoloDB learns from your confirmations, and how the High/Medium/Low confidence badge is computed. |
| 7 | [File map](07-file-map.md) | Every file in the repository with a one-line description. Use it as an index. |
| 8 | [Troubleshooting](08-troubleshooting.md) | "Something is wrong" → what it probably is → where to look in the code → how to fix it. |
| 9 | [Cost optimisation](09-cost-optimisation.md) | Where AI costs come from and every mechanism BoloDB uses to keep them low without hurting answer quality. |

## The one-paragraph summary

BoloDB lets anyone ask questions about a SQL database in plain English. When
you ask a question, BoloDB picks the handful of tables that matter
(chapter 4), sends the question plus that trimmed schema to OpenRouter
(chapter 3), checks the SQL that comes back before running it and
automatically fixes it if it's broken (chapter 5), runs it **read-only**
against your database, and shows the results with a plain-English restatement
and a confidence level (chapter 6). Every answer you confirm as correct is
remembered and makes future answers better.
