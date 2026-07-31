import json

# Slack caps a section's text at 3000 characters and a message at 50 blocks.
MAX_SECTION_TEXT = 3000
MAX_BLOCKS = 50

# Rows shown in a result table before it says "showing first N of M".
MAX_TABLE_ROWS = 10


def _fence_safe(text) -> str:
    """Text that cannot close a Slack code fence it is being placed inside.

    Cell values and generated SQL both go into ``` blocks, and either can
    contain a literal triple backtick — a column holding a snippet of markdown,
    or a SQL string literal. Slack ends the fence at the first one it sees, so
    the rest of the table renders as prose and any backticks after it re-open
    it. A zero-width space between the backticks is invisible in the rendered
    message and breaks the sequence.
    """
    return str(text).replace("```", "`\u200b``")


def loading_blocks(connection_name: str, question: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🤔 *Querying* `{connection_name}` …\n> {question}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Running SQL generation + execution. This may take a few seconds...",
                }
            ],
        },
    ]


def _table_block(columns: list, rows: list) -> dict:
    """A fenced text table of the first rows, trimmed to Slack's 3000 chars.

    Built once and then shortened a row at a time, rather than rebuilt from
    scratch each pass: the two used to be separate format strings that had to
    be kept identical, and a change to one silently produced a different table
    on the truncation path than on the normal one.
    """
    header = _fence_safe(" | ".join(str(c) for c in columns))
    rule = "—" * min(len(header), 60)
    total = len(rows)
    lines = [
        _fence_safe(" | ".join("NULL" if v is None else str(v) for v in row))
        for row in rows[:MAX_TABLE_ROWS]
    ]

    def render(visible: list[str]) -> str:
        body = "\n".join(visible)
        notice = (
            f"\n_Showing first {len(visible)} of {total} rows_"
            if len(visible) < total
            else ""
        )
        if not visible:
            # Every row was too wide to fit. An empty fence renders as a blank
            # grey box that looks like a bug; say what happened instead.
            return (
                f"*Results ({total} row{'s' if total != 1 else ''}):*\n"
                "_The rows are too wide to show in Slack — run the SQL above "
                "in BoloDB to see them._"
            )
        return (
            f"*Results ({total} row{'s' if total != 1 else ''}):*\n"
            f"```\n{header}\n{rule}\n{body}\n```{notice}"
        )

    text = render(lines)
    while len(text) > MAX_SECTION_TEXT and lines:
        lines.pop()
        text = render(lines)

    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def result_blocks(
    result: dict, question: str, conn_name: str | None = None
) -> list[dict]:
    blocks = []

    header_text = "*Results*"
    if conn_name:
        header_text += f" — `{conn_name}`"
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header_text},
        }
    )

    if not result.get("answered"):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "I wasn't able to answer that question. Please try rephrasing it.",
                },
            }
        )
        if result.get("execution_error"):
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Error: {result['execution_error']}",
                        }
                    ],
                }
            )
        return blocks

    if result.get("restatement"):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question:* {result['restatement']}",
                },
            }
        )

    if result.get("sql"):
        sql = _fence_safe(result["sql"])
        # Leave room for the "*SQL:*" label and the fence itself.
        budget = MAX_SECTION_TEXT - 20
        if len(sql) > budget:
            sql = sql[: budget - 3] + "..."
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*SQL:*\n```\n{sql}\n```"},
            }
        )

    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if columns and rows:
        blocks.append(_table_block(columns, rows))
    elif result.get("sql"):
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "SQL generated but no result rows to display.",
                },
            }
        )

    conf = result.get("confidence", "low")
    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
    confidence_text = f"{conf_emoji.get(conf, '⚪')} Confidence: {conf.title()}"
    if result.get("confidence_reason"):
        confidence_text += f" — {result['confidence_reason']}"

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": confidence_text}],
        }
    )

    return blocks


def error_blocks(error_message: str, question: str | None = None) -> list[dict]:
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "❌ *Query failed*"},
        },
    ]
    if question:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"> {question}"},
            }
        )
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": error_message},
        }
    )
    return blocks


def connection_picker_blocks(connections: list[dict], question: str) -> list[dict]:
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Which database should I query?\n> *{question}*",
            },
        },
        {"type": "divider"},
    ]

    # Slack enforces 50 blocks per message. Reserve space for header, divider,
    # context, and one connection row as margin, so cap at 45 connection rows.
    available = MAX_BLOCKS - 5
    shown = connections[:available]

    for conn in shown:
        alias = conn.get("alias_name") or conn.get("db_id", "?")[:8]
        dialect = conn.get("dialect", "unknown")
        table_count = conn.get("table_count", "?")

        value = json.dumps({"db_id": conn["db_id"], "q": question[:1800]})

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{alias}* — {dialect} ({table_count} tables)",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Query this →",
                        "emoji": True,
                    },
                    "value": value,
                    "action_id": "pick_connection",
                },
            }
        )

    extra = len(connections) - len(shown)
    notice = "Tip: Use `/ask connection_name: your question` to skip this step."
    if extra > 0:
        notice = (
            f"{extra} more connection{'s' if extra != 1 else ''} available. {notice}"
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": notice,
                }
            ],
        }
    )

    return blocks
