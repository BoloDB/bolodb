import logging

import backend.app.pgdatabase as mdb

log = logging.getLogger(__name__)


async def list_conversations(workspace_id):
    return await mdb.get_conversations(workspace_id)


async def create_conversation(workspace_id, title="", database_id=None):
    return await mdb.create_conversation(
        workspace_id, title=title, database_id=database_id
    )


async def get_conversation(workspace_id, conversation_id):
    return await mdb.get_conversation(workspace_id, conversation_id)


async def rename_conversation(workspace_id, conversation_id, title):
    return await mdb.rename_conversation(workspace_id, conversation_id, title)


async def delete_conversation(workspace_id, conversation_id):
    return await mdb.delete_conversation(workspace_id, conversation_id)


async def clear_conversations(workspace_id):
    return await mdb.clear_conversations(workspace_id)
