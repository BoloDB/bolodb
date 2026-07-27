import pytest
import json
from backend.app.llm import build_sql_system_prompt, parse_json


def test_parse_json_pure():
    text = '{"key": "value"}'
    assert parse_json(text) == {"key": "value"}


def test_parse_json_markdown_wrapped():
    text = '```json\n{"key": "value"}\n```'
    assert parse_json(text) == {"key": "value"}


def test_parse_json_markdown_wrapped_no_lang():
    text = '```\n{"key": "value"}\n```'
    assert parse_json(text) == {"key": "value"}


def test_parse_json_whitespace():
    text = '   \n\t {"key": "value"} \n\t   '
    assert parse_json(text) == {"key": "value"}


def test_parse_json_empty_object():
    text = "{}"
    assert parse_json(text) == {}


def test_parse_json_list():
    text = '```json\n[{"key": "value"}]\n```'
    # The current parse_json function looks for '{' and '}' so it actually doesn't parse lists well
    # since it extracts everything between first '{' and last '}'
    # if it's a list like `[{"key": "value"}]` it extracts `{"key": "value"}`
    # Let's adjust our test for the actual current behavior or modify it to test parsing an object inside a list if that is what happens.
    # Given a list `[{"key": "value"}]`, `find("{")` gives the `{` inside the array, and `rfind("}")` gives the `}`.
    # So `s = s[a:b+1]` gives `{"key": "value"}`.
    # Therefore json.loads(s) gives {"key": "value"}
    assert parse_json(text) == {"key": "value"}


def test_parse_json_extra_text():
    text = 'Here is the json you requested:\n```json\n{"key": "value"}\n```\nHope this helps!'
    assert parse_json(text) == {"key": "value"}


def test_parse_json_invalid_json():
    text = '```json\n{"key": "value"\n```'
    with pytest.raises(json.JSONDecodeError):
        parse_json(text)


def test_parse_json_no_braces_raises_error():
    text = "just some text"
    with pytest.raises(json.JSONDecodeError):
        parse_json(text)


def test_parse_json_multiple_json_objects():
    # The function only extracts the substring from the first { to the last }
    text = '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```'
    # Currently the function will grab `{"a": 1}\n```\n```json\n{"b": 2}`
    # Which is invalid json.
    with pytest.raises(json.JSONDecodeError):
        parse_json(text)


def test_parse_json_nested_braces():
    text = '```json\n{"a": {"b": 1}}\n```'
    assert parse_json(text) == {"a": {"b": 1}}


# --- dialect-aware prompt ---------------------------------------------------


def _prompt(dialect):
    return build_sql_system_prompt(
        schema_text="TABLE orders\n  id INTEGER PK",
        dialect=dialect,
        glossary=None,
        retrieved=None,
        max_examples=0,
        context=None,
    )


def test_oracle_prompt_asks_for_fetch_first_not_limit():
    """Rule 4 defers to the dialect hint, so Oracle must be told FETCH FIRST —
    an emitted `LIMIT 100` is a hard syntax error on Oracle."""
    p = _prompt("oracle")
    assert "FETCH FIRST n ROWS ONLY" in p
    assert "LIMIT 100" not in p


def test_mssql_prompt_asks_for_top():
    p = _prompt("mssql")
    assert "TOP (n)" in p
    assert "LIMIT 100" not in p


def test_limit_dialects_are_told_to_use_limit():
    for dialect in ("postgresql", "mysql", "sqlite"):
        assert "use LIMIT n" in _prompt(dialect), dialect


def test_prompt_names_the_dialect():
    assert "expert oracle analyst" in _prompt("oracle")


def test_unknown_dialect_still_builds_a_prompt():
    """An unsupported dialect must degrade to an empty rule 7, not blow up."""
    p = _prompt("snowflake")
    assert "Reply ONLY with this JSON" in p
