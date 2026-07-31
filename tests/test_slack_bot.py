"""Tests for the Slack `/ask` command handlers.

The handlers are the part of the integration that decides *what runs against
which database*, so these cover the routing decisions — parsing, connection
selection, and the checks that keep a button click from reaching a database it
was not offered — rather than the query pipeline underneath, which has its own
tests.
"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.integrations.slack import bot

WORKSPACE = str(uuid4())
INSTALLER = str(uuid4())
TEAM = "T0DEADBEEF"
RESPONSE_URL = "https://hooks.slack.com/commands/T0/1/abc"


def connection(db_id, alias, dialect="postgresql", tables=7):
    return {
        "db_id": db_id,
        "alias_name": alias,
        "dialect": dialect,
        "table_count": tables,
    }


@pytest.fixture
def install():
    return SimpleNamespace(workspace_id=WORKSPACE, user_id=INSTALLER)


@pytest.fixture
def slack_env(monkeypatch, install):
    """Stub the database lookups and capture launched queries.

    Returns the recorder, so a test can assert on exactly which (db_id,
    question) pair was dispatched — the thing that actually matters.
    """
    state = SimpleNamespace(install=install, connections=[], launched=[])

    async def get_installation_by_team(team_id):
        return state.install if team_id == TEAM else None

    async def get_recent_connections(workspace_id):
        assert workspace_id == WORKSPACE
        return state.connections

    monkeypatch.setattr(
        bot.mdb, "get_installation_by_team", get_installation_by_team, raising=False
    )
    monkeypatch.setattr(
        bot.mdb, "get_recent_connections", get_recent_connections, raising=False
    )
    monkeypatch.setattr(
        bot,
        "_run_query_and_respond",
        lambda question, workspace_id, db_id, *a, **kw: state.launched.append(
            (workspace_id, db_id, question)
        ),
    )
    return state


def slash(text, team_id=TEAM, response_url=RESPONSE_URL):
    return {"text": text, "team_id": team_id, "response_url": response_url}


async def call_slash(payload):
    return await bot.handle_slash_command(payload, None, None, None, None, None)


async def call_action(payload):
    return await bot.handle_interactive_callback(payload, None, None, None, None, None)


# --- parsing ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("sales: how many orders", ("sales", "how many orders")),
        ("  sales :  how many orders  ", ("sales", "how many orders")),
        ("prod db: revenue last month", ("prod db", "revenue last month")),
        ("how many orders", (None, "how many orders")),
        ("", (None, "")),
    ],
)
def test_parse_slash_command(text, expected):
    assert bot.parse_slash_command(text) == expected


def test_a_question_containing_a_colon_still_parses():
    """The prefix is a guess, not a grammar — the caller checks whether it names
    a real connection and falls back when it does not."""
    assert bot.parse_slash_command("revenue: by region") == ("revenue", "by region")


def test_a_multiline_question_keeps_its_body():
    """re.DOTALL, so a pasted multi-line question is not truncated at the first
    newline."""
    name, question = bot.parse_slash_command("sales: line one\nline two")
    assert name == "sales"
    assert question == "line one\nline two"


# --- slash command routing --------------------------------------------------


@pytest.mark.asyncio
async def test_an_empty_question_gets_usage_without_touching_the_database(slack_env):
    res = await call_slash(slash("   "))
    assert res["response_type"] == "ephemeral"
    assert "/ask" in res["text"]
    assert slack_env.launched == []


@pytest.mark.asyncio
async def test_an_unknown_team_is_told_to_install(slack_env):
    res = await call_slash(slash("how many orders", team_id="T0NOTINSTALLED"))
    assert "isn't connected" in res["text"]
    assert slack_env.launched == []


@pytest.mark.asyncio
async def test_a_workspace_with_no_connections_says_so(slack_env):
    slack_env.connections = []
    res = await call_slash(slash("how many orders"))
    assert "No database connections" in res["text"]
    assert slack_env.launched == []


@pytest.mark.asyncio
async def test_a_named_connection_runs_straight_away(slack_env):
    slack_env.connections = [connection("db-a", "sales"), connection("db-b", "hr")]
    res = await call_slash(slash("sales: how many orders"))
    assert slack_env.launched == [(WORKSPACE, "db-a", "how many orders")]
    assert "Querying sales" in res["text"]


@pytest.mark.asyncio
async def test_the_connection_name_is_matched_case_insensitively(slack_env):
    slack_env.connections = [connection("db-a", "Sales")]
    await call_slash(slash("SALES: how many orders"))
    assert slack_env.launched == [(WORKSPACE, "db-a", "how many orders")]


@pytest.mark.asyncio
async def test_an_unrecognised_prefix_falls_back_to_the_picker(slack_env):
    """ "revenue:" is a question, not a connection. Stripping it would silently
    change what the user asked, so the whole text goes to the picker."""
    slack_env.connections = [connection("db-a", "sales")]
    res = await call_slash(slash("revenue: by region"))
    assert slack_env.launched == []
    assert res["blocks"][0]["text"]["text"].endswith("*revenue: by region*")


@pytest.mark.asyncio
async def test_multiple_connections_offer_a_picker(slack_env):
    slack_env.connections = [connection("db-a", "sales"), connection("db-b", "hr")]
    res = await call_slash(slash("how many orders"))
    assert slack_env.launched == []
    buttons = [b for b in res["blocks"] if b.get("accessory")]
    assert len(buttons) == 2


@pytest.mark.asyncio
async def test_a_slash_command_without_a_response_url_is_refused(slack_env):
    """There is nowhere to deliver the answer, so starting the work would burn
    an LLM call for a result no one can ever see."""
    slack_env.connections = [connection("db-a", "sales")]
    res = await call_slash(slash("sales: how many orders", response_url=""))
    assert slack_env.launched == []
    assert "response_url" in res["text"]


# --- interactive callback ---------------------------------------------------


def action(db_id, question="how many orders", team=TEAM):
    import json

    return {
        "team": {"id": team},
        "response_url": RESPONSE_URL,
        "actions": [
            {
                "action_id": "pick_connection",
                "value": json.dumps({"db_id": db_id, "q": question}),
            }
        ],
    }


@pytest.mark.asyncio
async def test_picking_a_connection_runs_the_query(slack_env):
    slack_env.connections = [connection("db-a", "sales")]
    res = await call_action(action("db-a"))
    assert slack_env.launched == [(WORKSPACE, "db-a", "how many orders")]
    assert "Querying sales" in res["text"]


@pytest.mark.asyncio
async def test_a_db_id_outside_the_workspace_is_refused(slack_env):
    """The button value round-trips through Slack rather than being held server
    side. A db_id that is not among this workspace's connections must not reach
    the query pipeline, whether it is stale or crafted."""
    slack_env.connections = [connection("db-a", "sales")]
    res = await call_action(action("db-someone-elses"))
    assert slack_env.launched == []
    assert "no longer available" in res["text"]


@pytest.mark.asyncio
async def test_a_button_for_a_since_deleted_connection_is_refused(slack_env):
    slack_env.connections = []
    res = await call_action(action("db-a"))
    assert slack_env.launched == []
    assert "no longer available" in res["text"]


@pytest.mark.asyncio
async def test_an_unknown_action_id_is_ignored(slack_env):
    payload = action("db-a")
    payload["actions"][0]["action_id"] = "something_else"
    res = await call_action(payload)
    assert slack_env.launched == []
    assert res["text"] == "Unknown action."


@pytest.mark.asyncio
async def test_a_malformed_action_value_is_ignored(slack_env):
    payload = action("db-a")
    payload["actions"][0]["value"] = "{not json"
    res = await call_action(payload)
    assert slack_env.launched == []
    assert res["text"] == "Invalid action data."


@pytest.mark.asyncio
async def test_an_action_with_no_actions_is_ignored(slack_env):
    res = await call_action({"team": {"id": TEAM}, "actions": []})
    assert slack_env.launched == []
    assert res["text"] == "No action found."


# --- background execution ---------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_queries_are_capped(monkeypatch):
    """Nothing in the request path bounds this: /ask returns immediately and the
    work continues in the background, so without a cap a workspace typing faster
    than the queries finish piles them up without limit."""
    monkeypatch.setattr(bot, "MAX_CONCURRENT_QUERIES", 2)
    monkeypatch.setattr(bot, "_QUERY_SLOTS", None)

    live = 0
    peak = 0
    release = asyncio.Event()

    async def fake_run_query(*a, **kw):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await release.wait()
        live -= 1
        return {"answered": True, "sql": "SELECT 1", "columns": [], "rows": []}

    posted = []

    async def fake_post(url, body):
        posted.append(url)

    monkeypatch.setattr(bot, "_post_response", fake_post)
    monkeypatch.setattr(
        "backend.app.controllers.database.ensure_connection",
        _async_none,
    )
    monkeypatch.setattr("backend.app.controllers.query.run_query", fake_run_query)

    tasks = [
        asyncio.ensure_future(
            bot._execute_query(
                "q", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
            )
        )
        for _ in range(5)
    ]
    await asyncio.sleep(0.05)
    # Exactly the cap: fewer would mean the test never actually loaded it, and
    # the assertion would pass for a version with no limiter at all.
    assert peak == 2
    release.set()
    await asyncio.gather(*tasks)
    assert len(posted) == 5


async def _async_none(*a, **kw):
    return None


@pytest.mark.asyncio
async def test_a_query_that_overruns_reports_a_timeout(monkeypatch):
    monkeypatch.setattr(bot, "QUERY_TIMEOUT", 0.05)
    monkeypatch.setattr(bot, "_QUERY_SLOTS", None)

    async def hangs(*a, **kw):
        await asyncio.sleep(30)

    posted = []
    monkeypatch.setattr(bot, "_post_response", lambda url, body: _record(posted, body))
    monkeypatch.setattr(
        "backend.app.controllers.database.ensure_connection", _async_none
    )
    monkeypatch.setattr("backend.app.controllers.query.run_query", hangs)

    await bot._execute_query(
        "q", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
    )
    assert posted, "the user must be told the query was abandoned"
    text = str(posted[0])
    assert "took too long" in text


async def _record(sink, body):
    sink.append(body)


@pytest.mark.asyncio
async def test_the_timeout_covers_the_wait_for_a_concurrency_slot(monkeypatch):
    """Queueing is time the user is sitting in front of. With the acquire
    outside wait_for, the timeout bounded only the query, so a deeply queued one
    could outlive the 30 minutes Slack gives a response_url and finish with
    nowhere to deliver its answer."""
    monkeypatch.setattr(bot, "MAX_CONCURRENT_QUERIES", 1)
    monkeypatch.setattr(bot, "QUERY_TIMEOUT", 0.1)
    monkeypatch.setattr(bot, "_QUERY_SLOTS", None)

    release = asyncio.Event()

    async def holds_the_slot(*a, **kw):
        await release.wait()
        return {"answered": True, "sql": "", "columns": [], "rows": []}

    posted = []
    monkeypatch.setattr(bot, "_post_response", lambda url, body: _record(posted, body))
    monkeypatch.setattr(
        "backend.app.controllers.database.ensure_connection", _async_none
    )
    monkeypatch.setattr("backend.app.controllers.query.run_query", holds_the_slot)

    # The first query takes the only slot and holds it; the second can do
    # nothing but queue, and must time out rather than wait indefinitely.
    first = asyncio.ensure_future(
        bot._execute_query(
            "q1", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
        )
    )
    await asyncio.sleep(0.01)
    await bot._execute_query(
        "q2", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
    )

    assert posted, "the queued query must be answered, not abandoned"
    assert "took too long" in str(posted[0])

    release.set()
    await first


@pytest.mark.asyncio
async def test_a_failing_query_still_answers_the_user(monkeypatch):
    monkeypatch.setattr(bot, "_QUERY_SLOTS", None)

    async def boom(*a, **kw):
        raise RuntimeError("database on fire")

    posted = []
    monkeypatch.setattr(bot, "_post_response", lambda url, body: _record(posted, body))
    monkeypatch.setattr(
        "backend.app.controllers.database.ensure_connection", _async_none
    )
    monkeypatch.setattr("backend.app.controllers.query.run_query", boom)

    await bot._execute_query(
        "q", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
    )
    assert posted
    rendered = str(posted[0])
    assert "Query failed" in rendered
    # The internal failure is not quoted back into Slack.
    assert "database on fire" not in rendered


@pytest.mark.asyncio
async def test_shutdown_tells_users_their_query_was_abandoned(monkeypatch):
    """Without the drain a redeploy leaves every in-flight query showing
    "🤔 Querying …" forever, with no indication anything went wrong."""
    monkeypatch.setattr(bot, "_QUERY_SLOTS", None)
    started = asyncio.Event()

    async def hangs(*a, **kw):
        started.set()
        await asyncio.sleep(30)

    posted = []
    monkeypatch.setattr(bot, "_post_response", lambda url, body: _record(posted, body))
    monkeypatch.setattr(
        "backend.app.controllers.database.ensure_connection", _async_none
    )
    monkeypatch.setattr("backend.app.controllers.query.run_query", hangs)

    bot._run_query_and_respond(
        "q", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
    )
    await started.wait()
    assert await bot.drain_pending_queries(timeout=0.05) == 1
    assert posted, "a cancelled query must still say so"
    assert "restarted" in str(posted[0])


@pytest.mark.asyncio
async def test_draining_with_nothing_in_flight_is_a_no_op():
    assert await bot.drain_pending_queries(timeout=0.01) == 0


@pytest.mark.asyncio
async def test_a_launched_query_is_held_by_a_strong_reference(monkeypatch):
    """The event loop only keeps a weak reference to a running task, so one that
    nothing else holds can be garbage-collected mid-query."""
    monkeypatch.setattr(bot, "_QUERY_SLOTS", None)

    async def slow(*a, **kw):
        await asyncio.sleep(0.2)

    monkeypatch.setattr(bot, "_post_response", _async_none)
    monkeypatch.setattr(
        "backend.app.controllers.database.ensure_connection", _async_none
    )
    monkeypatch.setattr("backend.app.controllers.query.run_query", slow)

    before = len(bot._PENDING_TASKS)
    bot._run_query_and_respond(
        "q", WORKSPACE, "db-a", INSTALLER, RESPONSE_URL, *[None] * 5
    )
    assert len(bot._PENDING_TASKS) == before + 1
    await bot.drain_pending_queries(timeout=1.0)
    assert len(bot._PENDING_TASKS) == before
