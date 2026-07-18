from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    last_db_url: str | None = None


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
    conversation_id: str | None = None


class GlossaryItem(BaseModel):
    term: str
    maps_to: str = ""
    sql_hint: str = ""


class StarterItem(BaseModel):
    """A verified Q&A pair from onboarding starters."""

    question: str
    sql: str
    restatement: str = ""


class SaveOnboardReq(BaseModel):
    glossary: list[GlossaryItem] = []
    starters: list[StarterItem] = []


# ── Semantic catalog (issue #90) ──────────────────────────────────────


class ColumnDescription(BaseModel):
    """A plain-English meaning for one table column."""

    table: str
    column: str
    description: str = ""


class MetricDefinition(BaseModel):
    """A named business metric and the SQL expression that computes it."""

    name: str
    description: str = ""
    sql_expression: str = ""


class JoinPath(BaseModel):
    """A curated join between tables (which tables + the join condition)."""

    tables: str
    join_condition: str
    description: str = ""


class Synonym(BaseModel):
    """A business word mapped to a schema entity (table/column/metric)."""

    term: str
    entity_type: str = ""
    entity_name: str = ""


class ValueMapping(BaseModel):
    """A friendly business label for a stored categorical value."""

    table: str
    column: str
    db_value: str
    business_label: str = ""


class CatalogPayload(BaseModel):
    """The full semantic catalog for one database. Keys match
    ``KnowledgeBase.get_catalog`` / ``set_catalog``."""

    column_descriptions: list[ColumnDescription] = []
    metrics: list[MetricDefinition] = []
    joins: list[JoinPath] = []
    synonyms: list[Synonym] = []
    value_maps: list[ValueMapping] = []
