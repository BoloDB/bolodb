from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    # `provider` is accepted for backwards compatibility but ignored — Gemini
    # is currently the only AI provider (see backend/app/llm.py).
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    clear_api_key: bool = False


class ConnectReq(BaseModel):
    db_url: str


class ContextTurn(BaseModel):
    question: str
    sql: str
    restatement: str = ""


class QueryReq(BaseModel):
    question: str
    context: list[ContextTurn] = []
    conversation_id: str | None = None


class VerifyReq(BaseModel):
    question: str
    sql: str
    restatement: str = ""


class FeedbackReq(BaseModel):
    query_id: str = ""
    verdict: str
    reason: str = ""
    question: str = ""
    sql: str = ""
    restatement: str = ""


class RawSQLReq(BaseModel):
    sql: str


class GlossaryItem(BaseModel):
    term: str
    maps_to: str = ""
    sql_hint: str = ""


class SaveOnboardReq(BaseModel):
    glossary: list[GlossaryItem] = []
    starters: list[dict] = []
