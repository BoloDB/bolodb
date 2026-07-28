import json


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
        sql = result["sql"]
        if len(sql) > 3000:
            sql = sql[:2997] + "..."
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*SQL:*\n```\n{sql}\n```"},
            }
        )

    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if columns and rows:
        max_rows = 10
        display_rows = rows[:max_rows]
        truncated = len(rows) > max_rows

        header_row = " | ".join(str(c) for c in columns)
        line_rows = []
        for row in display_rows:
            line_rows.append(
                " | ".join(str(v) if v is not None else "NULL" for v in row)
            )

        table_text = (
            f"*Results ({len(rows)} row{'s' if len(rows) != 1 else ''}):*\n"
            f"```\n{header_row}\n{'—' * min(len(header_row), 60)}\n"
            + "\n".join(line_rows)
            + "\n```"
        )
        if truncated:
            table_text += f"\n_Showing first {max_rows} of {len(rows)} rows_"

        if len(table_text) > 3000:
            while len(table_text) > 3000 and line_rows:
                line_rows.pop()
                table_text = (
                    f"*Results ({len(rows)} row{'s' if len(rows) != 1 else ''}):*\n"
                    f"```\n{header_row}\n{'—' * min(len(header_row), 60)}\n"
                    + "\n".join(line_rows)
                    + "\n```"
                )
                if truncated:
                    remaining = len(rows) - len(line_rows) + max_rows
                    table_text += (
                        f"\n_Showing first {len(line_rows)} of {remaining} rows_"
                    )

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": table_text},
            }
        )
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

    for conn in connections:
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

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Tip: Use `/ask connection_name: your question` to skip this step.",
                }
            ],
        }
    )

    return blocks
