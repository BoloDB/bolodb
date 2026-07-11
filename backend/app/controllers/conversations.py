import backend.app.mongodatabase as mdb


def list_conversations(user_id):
    return mdb.get_conversations(user_id)


def create_conversation(user_id, title="", database_id=None):
    return mdb.create_conversation(user_id, title=title, database_id=database_id)


def get_conversation(user_id, conversation_id):
    return mdb.get_conversation(user_id, conversation_id)


def rename_conversation(user_id, conversation_id, title):
    return mdb.rename_conversation(user_id, conversation_id, title)


def delete_conversation(user_id, conversation_id):
    return mdb.delete_conversation(user_id, conversation_id)


def clear_conversations(user_id):
    return mdb.clear_conversations(user_id)
