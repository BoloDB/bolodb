from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    ollama_url: str | None = None
    api_key: str | None = None


class ConnectReq(BaseModel):
    db_url: str


class ContextTurn(BaseModel):
    question: str
    sql: str
    restatement: str = ""


class QueryReq(BaseModel):
    question: str
    context: list[ContextTurn] = []


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
