# BoloDB Documentation

Welcome! These docs explain **what BoloDB does, how it does it, and where in the code each piece lives**.

- A **non-technical reader** can follow every chapter top-to-bottom and understand the product architecture.
- A **developer** can jump from any paragraph straight into the codebase, annotated with file and function references.

---

## Chapters

| # | Chapter | What it answers |
|---|---------|-----------------|
| 1 | [What is BoloDB?](01-what-is-bolodb.md) | Multi-tenant product introduction, security model, and 30-second architecture overview. |
| 2 | [How a question becomes an answer](02-how-a-question-becomes-an-answer.md) | The full execution pipeline step by step. **The most important chapter.** |
| 3 | [The AI layer (OpenRouter)](03-the-ai-layer-openrouter.md) | OpenRouter provider (`deepseek/deepseek-v4-flash`), structured JSON outputs, streaming SSE, and prompt assembly. |
| 4 | [Schema linking — choosing tables](04-schema-linking.md) | How table scoring, FK expansion, and two-stage linking optimize context windows. |
| 5 | [Safety, validation and self-repair](05-safety-validation-and-self-repair.md) | SSRF defense, read-only AST safety, static SQL validation, statement timeouts, and self-repair. |
| 6 | [Learning, trust and confidence](06-learning-trust-and-confidence.md) | PostgreSQL knowledge base, Jaccard/sequence similarity, and confidence badges. |
| 7 | [File map](07-file-map.md) | Complete codebase index mapping backend, frontend, tests, and configurations. |
| 8 | [Troubleshooting](08-troubleshooting.md) | Symptom-based troubleshooting guide for users and maintainers. |
| 9 | [Cost optimisation](09-cost-optimisation.md) | Token optimization mechanisms, structured output contracts, and budget controls. |
| 10 | [Authentication and Workspaces](10-auth-and-workspaces.md) | JWT auth, Google OAuth, workspace multi-tenancy, and RBAC permission matrix. |
| 11 | [Dashboards and Charts](11-dashboards-and-charts.md) | Interactive ECharts visualizations, saved queries, and dashboard panel CRUD. |
| 12 | [The Semantic Layer](12-semantic-layer.md) | Business metrics, join rules, synonyms, value mappings, and domain context injection. |

---

## The Summary

BoloDB lets anyone talk to their database in plain English. Built as a multi-tenant FastAPI + SvelteKit web application, it translates questions into SQL using OpenRouter AI (`deepseek/deepseek-v4-flash`), validates and executes queries safely in read-only mode, and renders interactive ECharts visualizations and restatements. Every request is scoped to a workspace and database connection via `X-Workspace-Id` and `X-Db-Id` headers. Every confirmed query enriches the workspace's PostgreSQL knowledge base to improve future accuracy.
