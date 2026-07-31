"""Tests for the Slack Block Kit builders.

Slack rejects a whole message if any section's text exceeds 3000 characters or
the message carries more than 50 blocks, so a result that overruns either does
not render badly — it does not render at all, and the user sees nothing come
back from a query that actually succeeded.
"""

import json

import pytest

from backend.app.integrations.slack.blocks import (
    MAX_BLOCKS,
    MAX_SECTION_TEXT,
    connection_picker_blocks,
    error_blocks,
    loading_blocks,
    result_blocks,
)


def section_texts(blocks):
    out = []
    for b in blocks:
        if b.get("type") == "section":
            out.append(b["text"]["text"])
        elif b.get("type") == "context":
            out.extend(e["text"] for e in b["elements"])
    return out


def assert_within_slack_limits(blocks):
    assert len(blocks) <= MAX_BLOCKS
    for text in section_texts(blocks):
        assert len(text) <= MAX_SECTION_TEXT, f"section is {len(text)} chars"


def result(**overrides):
    base = {
        "answered": True,
        "sql": "SELECT 1",
        "columns": ["id", "name"],
        "rows": [[1, "alice"], [2, None]],
        "confidence": "high",
    }
    base.update(overrides)
    return base


# --- results ----------------------------------------------------------------


def test_a_normal_result_renders_sql_rows_and_confidence():
    blocks = result_blocks(result(), "who")
    text = "\n".join(section_texts(blocks))
    assert "SELECT 1" in text
    assert "alice" in text
    assert "Confidence: High" in text
    assert_within_slack_limits(blocks)


def test_a_null_cell_is_shown_as_NULL_not_None():
    text = "\n".join(section_texts(result_blocks(result(), "who")))
    assert "NULL" in text
    assert "None" not in text


def test_an_unanswered_result_says_so_and_stops():
    blocks = result_blocks(result(answered=False, execution_error="boom"), "who")
    text = "\n".join(section_texts(blocks))
    assert "wasn't able to answer" in text
    assert "boom" in text
    assert "SELECT 1" not in text


def test_a_cell_containing_a_code_fence_cannot_break_out_of_the_table():
    """Slack ends a fenced block at the first ``` it sees. A column holding a
    markdown snippet would otherwise close the table early, rendering the rest
    as prose and re-opening the fence on the next backticks."""
    blocks = result_blocks(
        result(rows=[[1, "before ``` after"]]),
        "who",
    )
    table = [t for t in section_texts(blocks) if "before" in t][0]
    # Exactly two fences: the ones this builder opened and closed.
    assert table.count("```") == 2


def test_sql_containing_a_code_fence_cannot_break_out_either():
    blocks = result_blocks(result(sql="SELECT '```' AS x"), "who")
    sql_block = [t for t in section_texts(blocks) if t.startswith("*SQL:*")][0]
    assert sql_block.count("```") == 2


def test_a_very_wide_result_is_trimmed_to_fit():
    wide = [[i, "x" * 400] for i in range(10)]
    blocks = result_blocks(result(rows=wide), "who")
    assert_within_slack_limits(blocks)
    table = [t for t in section_texts(blocks) if "Results (" in t][0]
    assert "Showing first" in table


def test_a_result_whose_every_row_is_too_wide_does_not_emit_an_empty_fence():
    """Trimming can run out of rows. An empty ``` block renders as a blank grey
    box that reads as a bug, so say what happened instead."""
    blocks = result_blocks(result(rows=[["x" * 5000]], columns=["huge"]), "who")
    assert_within_slack_limits(blocks)
    table = [t for t in section_texts(blocks) if "Results (" in t][0]
    assert "```\n\n```" not in table
    assert "too wide" in table


def test_enormous_sql_is_truncated_rather_than_rejected_by_slack():
    blocks = result_blocks(result(sql="SELECT " + "a," * 5000 + "1"), "who")
    assert_within_slack_limits(blocks)
    sql_block = [t for t in section_texts(blocks) if t.startswith("*SQL:*")][0]
    assert sql_block.endswith("...\n```")


def test_the_row_total_reflects_the_whole_result_not_the_shown_rows():
    """The count is what the query returned; the table is only what fits."""
    blocks = result_blocks(result(rows=[[i, "n"] for i in range(500)]), "who")
    table = [t for t in section_texts(blocks) if "Results (" in t][0]
    assert "Results (500 rows)" in table
    assert "Showing first" in table


def test_one_row_is_not_pluralised():
    blocks = result_blocks(result(rows=[[1, "alice"]]), "who")
    assert "Results (1 row)" in "\n".join(section_texts(blocks))


def test_sql_with_no_rows_says_so():
    blocks = result_blocks(result(rows=[], columns=[]), "who")
    assert "no result rows" in "\n".join(section_texts(blocks))


@pytest.mark.parametrize("conf", ["high", "medium", "low", "unheard-of"])
def test_every_confidence_value_renders(conf):
    blocks = result_blocks(result(confidence=conf), "who")
    assert "Confidence:" in "\n".join(section_texts(blocks))


# --- picker -----------------------------------------------------------------


def test_the_picker_offers_a_button_per_connection():
    conns = [
        {
            "db_id": f"db-{i}",
            "alias_name": f"c{i}",
            "dialect": "postgresql",
            "table_count": 3,
        }
        for i in range(4)
    ]
    blocks = connection_picker_blocks(conns, "how many orders")
    buttons = [b["accessory"] for b in blocks if b.get("accessory")]
    assert len(buttons) == 4
    assert json.loads(buttons[0]["value"])["db_id"] == "db-0"
    assert_within_slack_limits(blocks)


def test_a_workspace_with_more_connections_than_slack_allows_still_renders():
    conns = [
        {
            "db_id": f"db-{i}",
            "alias_name": f"c{i}",
            "dialect": "postgresql",
            "table_count": 3,
        }
        for i in range(200)
    ]
    blocks = connection_picker_blocks(conns, "how many orders")
    assert_within_slack_limits(blocks)
    assert "more connection" in section_texts(blocks)[-1]


def test_a_connection_without_an_alias_falls_back_to_its_id():
    conns = [{"db_id": "abcdef123456", "dialect": "duckdb", "table_count": 1}]
    blocks = connection_picker_blocks(conns, "q")
    assert "abcdef12" in section_texts(blocks)[1]


def test_the_button_value_stays_inside_slacks_2000_character_cap():
    conns = [
        {
            "db_id": "d" * 40,
            "alias_name": "a",
            "dialect": "postgresql",
            "table_count": 1,
        }
    ]
    blocks = connection_picker_blocks(conns, "q" * 5000)
    value = [b["accessory"]["value"] for b in blocks if b.get("accessory")][0]
    assert len(value) <= 2000


# --- other builders ---------------------------------------------------------


def test_loading_blocks_name_the_connection_and_echo_the_question():
    blocks = loading_blocks("sales", "how many orders")
    text = "\n".join(section_texts(blocks))
    assert "sales" in text
    assert "how many orders" in text
    assert_within_slack_limits(blocks)


def test_error_blocks_carry_the_message_and_the_question():
    blocks = error_blocks("it broke", "how many orders")
    text = "\n".join(section_texts(blocks))
    assert "it broke" in text
    assert "how many orders" in text
    assert_within_slack_limits(blocks)


def test_error_blocks_work_without_a_question():
    assert_within_slack_limits(error_blocks("it broke"))
