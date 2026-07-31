from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.serialization import _to_uuid
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert

from sqlalchemy import select, delete
from backend.app.models.orm_slack import SlackInstallation

logger = logging.getLogger(__name__)


class SlackTeamConflictError(RuntimeError):
    """Raised when a Slack team is already installed on a different workspace."""


async def save_installation(
    team_id: str,
    team_name: str,
    bot_token: str,
    bot_user_id: str,
    user_id: str,
    workspace_id: str,
    scopes: str,
):
    wid = _to_uuid(workspace_id)
    uid = _to_uuid(user_id)
    async with async_session() as session:
        try:
            # This workspace's previous installation, if it was of a *different*
            # Slack team, has to go — uq_slack_installations_workspace allows
            # only one. The row for this same team, if any, is left for the
            # upsert below to update in place.
            await session.execute(
                delete(SlackInstallation).where(
                    SlackInstallation.workspace_id == wid,
                    SlackInstallation.team_id != team_id,
                )
            )
            # The conflict clause is where the cross-workspace check lives, not
            # a SELECT beforehand: a check-then-insert is two statements with a
            # gap between them, and two installs of the same Slack team racing
            # through that gap would both pass, the loser's upsert silently
            # rewriting workspace_id and moving the installation out from under
            # the workspace that owns it. Restricting the update to rows this
            # workspace already owns makes the database itself refuse that, and
            # a hit that updates nothing is the conflict.
            s = (
                pg_insert(SlackInstallation)
                .values(
                    team_id=team_id,
                    team_name=team_name,
                    bot_token=bot_token,
                    bot_user_id=bot_user_id,
                    user_id=uid,
                    workspace_id=wid,
                    scopes=scopes,
                )
                .on_conflict_do_update(
                    index_elements=["team_id"],
                    set_=dict(
                        team_name=team_name,
                        bot_token=bot_token,
                        bot_user_id=bot_user_id,
                        user_id=uid,
                        workspace_id=wid,
                        scopes=scopes,
                    ),
                    where=SlackInstallation.workspace_id == wid,
                )
            )
            result = await session.execute(s)
            if result.rowcount == 0:
                raise SlackTeamConflictError(
                    "This Slack workspace is already connected to a different BoloDB workspace."
                )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_installation_by_team(team_id):
    async with async_session() as session:
        result = await session.execute(
            select(SlackInstallation).where(SlackInstallation.team_id == team_id)
        )
        install = result.scalar_one_or_none()
        if install is None:
            return None
        return install


async def get_installations_by_workspace(workspace_id):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(SlackInstallation).where(SlackInstallation.workspace_id == wid)
        )
        return result.scalars().all()


async def delete_installation_for_workspace(team_id, workspace_id):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(SlackInstallation).where(
                    SlackInstallation.team_id == team_id,
                    SlackInstallation.workspace_id == wid,
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise
