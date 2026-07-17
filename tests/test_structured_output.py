"""Tests for structured SQL output: schema, tolerant parser, generate_sql wiring (#94)."""

import asyncio

from backend.app.llm import SQL_SCHEMA, generate_sql, parse_sql_output


# --- parse_sql_output -------------------------------------------------------


def test_parse_dict_input_normalized():
    out = parse_sql_output(
        {"sql": "SELECT 1", "restatement": "one", "assumptions": ["a"]}
    )
    assert out == {"sql": "SELECT 1", "restatement": "one", "assumptions": ["a"]}


def test_parse_plain_json_text():
    out = parse_sql_output('{"sql": "SELECT 1", "restatement": "one"}')
    assert out["sql"] == "SELECT 1"
    assert out["restatement"] == "one"
    assert out["assumptions"] == []  # missing -> default empty list


def test_parse_fenced_and_prose_wrapped_json():
    raw = 'Sure!\n```json\n{"sql": "SELECT 2", "restatement": "two"}\n```\nDone.'
    out = parse_sql_output(raw)
    assert out["sql"] == "SELECT 2"


def test_assumptions_as_string_becomes_list():
    out = parse_sql_output({"sql": "x", "restatement": "y", "assumptions": "just one"})
    assert out["assumptions"] == ["just one"]


def test_assumptions_list_filters_empties_and_stringifies():
    out = parse_sql_output(
        {"sql": "x", "restatement": "y", "assumptions": ["keep", "", "  ", 7]}
    )
    assert out["assumptions"] == ["keep", "7"]


def test_blank_assumptions_string_is_empty_list():
    out = parse_sql_output({"sql": "x", "restatement": "y", "assumptions": "   "})
    assert out["assumptions"] == []


def test_non_object_json_yields_defaults():
    # A JSON array isn't a valid response object -> safe defaults, no raise.
    out = parse_sql_output("[1, 2, 3]")
    assert out == {"sql": "", "restatement": "", "assumptions": []}


def test_garbage_text_yields_defaults():
    out = parse_sql_output("the model said no")
    assert out == {"sql": "", "restatement": "", "assumptions": []}


def test_non_string_sql_is_stringified():
    out = parse_sql_output({"sql": 123, "restatement": None})
    assert out["sql"] == "123"
    assert out["restatement"] == ""  # None -> default ""


def test_empty_dict_defaults():
    assert parse_sql_output({}) == {"sql": "", "restatement": "", "assumptions": []}


# --- SQL_SCHEMA -------------------------------------------------------------


def test_schema_shape():
    assert SQL_SCHEMA["name"] == "sql_result"
    schema = SQL_SCHEMA["schema"]
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"sql", "restatement", "assumptions"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["assumptions"]["type"] == "array"


# --- generate_sql wiring ----------------------------------------------------


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def complete(self, system, user, json_mode=False, schema=None):
        self.calls.append(
            {"system": system, "user": user, "json_mode": json_mode, "schema": schema}
        )
        return self._responses.pop(0)

    async def health_check(self):
        return {"ok": True}


def _gen(provider, question="How many orders?"):
    return asyncio.run(
        generate_sql(
            provider,
            question,
            schema_text="orders(id, total_amount)",
            dialect="sqlite",
            glossary=[],
            retrieved=[],
        )
    )


def test_generate_sql_returns_typed_output_and_passes_schema():
    provider = FakeProvider(
        [
            '{"sql": "SELECT COUNT(*) FROM orders", "restatement": "count", '
            '"assumptions": ["counted all rows"]}'
        ]
    )
    out = _gen(provider)
    assert out["sql"] == "SELECT COUNT(*) FROM orders"
    assert out["assumptions"] == ["counted all rows"]
    # one call, structured schema forwarded, json mode on
    assert len(provider.calls) == 1
    assert provider.calls[0]["schema"] is SQL_SCHEMA
    assert provider.calls[0]["json_mode"] is True
    # prompt asks the model for assumptions
    assert "assumptions" in provider.calls[0]["system"]


def test_generate_sql_retries_once_on_empty_output():
    provider = FakeProvider(
        ["not json at all", '{"sql": "SELECT 1", "restatement": "ok"}']
    )
    out = _gen(provider)
    assert out["sql"] == "SELECT 1"
    assert len(provider.calls) == 2  # retried after the unusable first response


def test_generate_sql_no_retry_when_first_is_good():
    provider = FakeProvider(['{"sql": "SELECT 1", "restatement": "ok"}', "unused"])
    out = _gen(provider)
    assert out["sql"] == "SELECT 1"
    assert len(provider.calls) == 1
