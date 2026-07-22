from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from backend.app.models.base import Base, _utcnow, _uuid7


class Dashboard(Base):
    __tablename__ = "dashboards"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid7)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    description = Column(String)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    panels = relationship(
        "DashboardPanel", back_populates="dashboard", cascade="all, delete"
    )


class DashboardPanel(Base):
    __tablename__ = "dashboard_panels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid7)
    dashboard_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.id", ondelete="CASCADE"),
        nullable=False,
    )
    saved_query_id = Column(
        UUID(as_uuid=True), ForeignKey("saved_queries.id", ondelete="SET NULL")
    )
    title = Column(String(255))
    visualization_type = Column(String)
    viz_config = Column(JSONB, default=lambda: {})
    position = Column(JSONB, default=lambda: {"x": 0, "y": 0, "w": 4, "h": 4})
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    dashboard = relationship("Dashboard", back_populates="panels")
