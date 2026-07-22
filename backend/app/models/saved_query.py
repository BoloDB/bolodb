from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from backend.app.models.base import Base, _utcnow, _uuid7


class SavedQuery(Base):
    __tablename__ = "saved_queries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid7)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name = Column(String(255), nullable=False)
    description = Column(String)
    question = Column(String)
    sql = Column(String)
    columns = Column(JSONB)
    database_id = Column(String)
    visualization_type = Column(String, default="table")
    viz_config = Column(JSONB, default=lambda: {})
    last_result = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
