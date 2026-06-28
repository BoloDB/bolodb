"""Tests for the generate→validate→(execute)→repair loop (issue #95)."""

from backend.app.repair import run_repair_loop, schema_validator


class FakeGenerator:
    """Returns queued candidates in order; records the feedback it was given."""

    def __init__(self, candidates):
        self._candidates = list(candidates)
        self.feedback_log = []
        self.calls = 0

    def __call__(self, feedback):
        self.feedback_log.append(feedback)
        self.calls += 1
        if self._candidates:
            return self._candidates.pop(0)
        return {"sql": "", "restatement": ""}


def ok_validate(_sql):
    return {"ok": True, "errors": []}


def test_first_attempt_success_no_executor():
    gen = FakeGenerator([{"sql": "SELECT 1", "restatement": "one"}])
    res = run_repair_loop(gen, ok_validate)
    assert res["ok"] is True
    assert res["sql"] == "SELECT 1"
    assert res["restatement"] == "one"
    assert res["result"] is None
    assert [a["stage"] for a in res["attempts"]] == ["ok"]
    assert gen.calls == 1
    assert gen.feedback_log == [""]  # no feedback on the first attempt


def test_validation_failure_then_repair():
    gen = FakeGenerator(
        [
            {"sql": "SELECT revenue FROM orders", "restatement": "bad"},
            {"sql": "SELECT total_amount FROM orders", "restatement": "good"},
        ]
    )

    def validate(sql):
        if "revenue" in sql:
            return {
                "ok": False,
                "errors": ["Unknown column: 'revenue' does not exist."],
            }
        return {"ok": True, "errors": []}

    res = run_repair_loop(gen, validate)
    assert res["ok"] is True
    assert res["sql"] == "SELECT total_amount FROM orders"
    assert [a["stage"] for a in res["attempts"]] == ["validate", "ok"]
    # the repair attempt received feedback naming the prior error + SQL
    assert "revenue" in gen.feedback_log[1]
    assert "SELECT revenue FROM orders" in gen.feedback_log[1]


def test_execution_failure_then_repair():
    gen = FakeGenerator(
        [
            {"sql": "SELECT * FROM orders WHERE bad", "restatement": "x"},
            {"sql": "SELECT * FROM orders", "restatement": "y"},
        ]
    )
    calls = {"n": 0}

    def execute(sql):
        calls["n"] += 1
        if "WHERE bad" in sql:
            return {"error": "syntax error near 'bad'"}
        return {"columns": ["id"], "rows": [[1]]}

    res = run_repair_loop(gen, ok_validate, execute=execute)
    assert res["ok"] is True
    assert res["result"] == {"columns": ["id"], "rows": [[1]]}
    assert [a["stage"] for a in res["attempts"]] == ["execute", "ok"]
    assert "syntax error" in gen.feedback_log[1]
    assert calls["n"] == 2


def test_exhausts_iterations_when_never_fixed():
    gen = FakeGenerator(
        [{"sql": f"SELECT bad{i}", "restatement": ""} for i in range(5)]
    )

    def validate(_sql):
        return {"ok": False, "errors": ["nope"]}

    res = run_repair_loop(gen, validate, max_iterations=3)
    assert res["ok"] is False
    assert len(res["attempts"]) == 3
    assert all(a["stage"] == "validate" for a in res["attempts"])
    assert gen.calls == 3
    assert res["sql"] == "SELECT bad2"  # last attempt is surfaced


def test_validation_only_success_when_no_executor():
    gen = FakeGenerator([{"sql": "SELECT 1"}])
    res = run_repair_loop(gen, ok_validate, execute=None)
    assert res["ok"] is True
    assert res["result"] is None


def test_latency_budget_stops_early():
    # clock() is called once for `start`, then before each subsequent attempt.
    # start=0; the pre-attempt-2 check returns 100 (> budget) → loop stops.
    ticks = iter([0, 100, 100, 100, 100])

    gen = FakeGenerator([{"sql": "SELECT bad"} for _ in range(5)])

    def validate(_sql):
        return {"ok": False, "errors": ["nope"]}

    res = run_repair_loop(
        gen,
        validate,
        max_iterations=5,
        max_seconds=10,
        clock=lambda: next(ticks),
    )
    assert res["ok"] is False
    # first attempt runs; budget exceeded before the second → only 1 attempt
    assert gen.calls == 1
    assert len(res["attempts"]) == 1


def test_max_iterations_floor_runs_at_least_once():
    gen = FakeGenerator([{"sql": "SELECT 1"}])
    res = run_repair_loop(gen, ok_validate, max_iterations=0)
    assert gen.calls == 1
    assert res["ok"] is True


def test_schema_validator_integration():
    schema = {
        "orders": {
            "columns": [{"name": "id"}, {"name": "total_amount"}],
            "foreign_keys": [],
        }
    }
    validate = schema_validator(schema, dialect="sqlite")

    good = FakeGenerator([{"sql": "SELECT total_amount FROM orders"}])
    assert run_repair_loop(good, validate)["ok"] is True

    bad = FakeGenerator([{"sql": "SELECT revenue FROM orders"}])
    out = run_repair_loop(bad, validate, max_iterations=1)
    assert out["ok"] is False
    assert "revenue" in out["attempts"][0]["errors"][0]
