from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.serialization import _to_uuid
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert

from sqlalchemy import select, delete
from backend.app.models.orm_slack import SlackInstallation

logger = logging.getLogger(__name__)


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
            await session.execute(
                delete(SlackInstallation).where(SlackInstallation.workspace_id == wid)
            )
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
                )
            )
            await session.execute(s)
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


async def get_installation_by_user(user_id):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(SlackInstallation).where(SlackInstallation.user_id == uid)
        )
        install = result.scalars().all()
        return install


async def delete_installation(team_id):
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(SlackInstallation).where(SlackInstallation.team_id == team_id)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


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
