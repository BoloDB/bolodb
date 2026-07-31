"""Tests for persisting a Slack installation.

A Slack team maps to exactly one BoloDB workspace and vice versa, and the
installation carries the bot token and the identity every `/ask` runs under.
Getting the conflict handling wrong does not corrupt a row — it hands one
workspace's Slack app to another, so the statements are asserted directly.
"""

from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import backend.app.pgdatabase.slack as slack_db
from backend.app.models.orm_slack import SlackInstallation
from backend.app.pgdatabase.slack import SlackTeamConflictError

WORKSPACE = str(uuid4())
OTHER_USER = str(uuid4())
TEAM = "T0DEADBEEF"


class FakeResult:
    def __init__(self, rowcount=1):
        self.rowcount = rowcount


class FakeSession:
    """Records every statement, and reports whatever rowcount a test asks for."""

    def __init__(self, rowcounts=None):
        self.statements = []
        self.rowcounts = list(rowcounts or [])
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement, *a, **kw):
        self.statements.append(statement)
        rowcount = self.rowcounts.pop(0) if self.rowcounts else 1
        return FakeResult(rowcount)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def session(monkeypatch):
    fake = FakeSession()
    monkeypatch.setattr(slack_db, "async_session", lambda: fake)
    return fake


def compiled(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    )


async def save(**overrides):
    kwargs = dict(
        team_id=TEAM,
        team_name="Acme",
        bot_token="encrypted",
        bot_user_id="U1",
        user_id=OTHER_USER,
        workspace_id=WORKSPACE,
        scopes="commands,chat:write",
    )
    kwargs.update(overrides)
    return await slack_db.save_installation(**kwargs)


@pytest.mark.asyncio
async def test_a_fresh_install_is_written_and_committed(session):
    await save()
    assert session.committed
    assert not session.rolled_back


@pytest.mark.asyncio
async def test_the_workspaces_previous_install_of_another_team_is_removed(session):
    """uq_slack_installations_workspace allows only one row per workspace, so
    reconnecting to a different Slack team has to clear the old one."""
    await save()
    delete_sql = compiled(session.statements[0])
    assert "DELETE FROM slack_installations" in delete_sql
    assert "workspace_id" in delete_sql
    # ...but not the row for this same team, which the upsert updates in place.
    assert "team_id !=" in delete_sql


@pytest.mark.asyncio
async def test_the_upsert_refuses_rows_belonging_to_another_workspace(session):
    """The cross-workspace check lives in the conflict clause, not in a SELECT
    beforehand: a check-then-insert is two statements with a gap between them,
    and two installs of the same Slack team racing through that gap would both
    pass, the loser's upsert silently moving the installation."""
    await save()
    upsert_sql = compiled(session.statements[1])
    assert "ON CONFLICT" in upsert_sql
    assert "DO UPDATE" in upsert_sql
    assert "WHERE slack_installations.workspace_id" in upsert_sql


@pytest.mark.asyncio
async def test_a_team_already_installed_elsewhere_is_a_conflict(monkeypatch):
    """The guarded update matches nothing, which is how the database reports
    that this Slack team belongs to someone else."""
    fake = FakeSession(rowcounts=[1, 0])
    monkeypatch.setattr(slack_db, "async_session", lambda: fake)

    with pytest.raises(SlackTeamConflictError):
        await save()
    assert fake.rolled_back
    assert not fake.committed


@pytest.mark.asyncio
async def test_a_failure_rolls_back(monkeypatch):
    class Exploding(FakeSession):
        async def execute(self, statement, *a, **kw):
            raise RuntimeError("connection lost")

    fake = Exploding()
    monkeypatch.setattr(slack_db, "async_session", lambda: fake)

    with pytest.raises(RuntimeError):
        await save()
    assert fake.rolled_back
    assert not fake.committed


@pytest.mark.asyncio
async def test_a_delete_is_scoped_to_the_workspace(monkeypatch):
    """Removing an installation must never reach another workspace's row."""
    fake = FakeSession()
    monkeypatch.setattr(slack_db, "async_session", lambda: fake)

    assert await slack_db.delete_installation_for_workspace(TEAM, WORKSPACE) is True
    sql = compiled(fake.statements[0])
    assert "team_id" in sql
    assert "workspace_id" in sql


@pytest.mark.asyncio
async def test_deleting_something_that_is_not_there_reports_false(monkeypatch):
    fake = FakeSession(rowcounts=[0])
    monkeypatch.setattr(slack_db, "async_session", lambda: fake)
    assert await slack_db.delete_installation_for_workspace(TEAM, WORKSPACE) is False


def test_no_unscoped_delete_is_exported():
    """An unscoped `delete_installation(team_id)` sitting in the mdb namespace
    next to the scoped one is a footgun with no caller."""
    import backend.app.pgdatabase as mdb

    assert not hasattr(mdb, "delete_installation")
    assert hasattr(mdb, "delete_installation_for_workspace")


def test_the_bot_token_column_is_never_returned_to_a_client():
    """The response model is what /installations serialises through, so a token
    can only leak if someone adds it here."""
    from backend.app.integrations.slack.models import SlackInstallationResponse

    assert "bot_token" not in SlackInstallationResponse.model_fields
    assert "bot_token" in SlackInstallation.__table__.columns
