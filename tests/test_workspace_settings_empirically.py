"""Empirical verification test suite for WorkspaceSettings model defaults and Alembic migration e8f901a23b4c.

Written by Challenger 2 to stress test model constraints, defaults, JSONB serialization,
and migration DDL definitions.
"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import create_engine, select, String, Integer, DateTime
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, declarative_base

from backend.app.models.workspace_settings import WorkspaceSettings
from backend.alembic.versions import (
    e8f901a23b4c_add_workspace_settings_table as migration,
)

SQLiteTestBase = declarative_base()


# =====================================================================
# 1. MODEL DEFAULTS AND CONSTRAINT VERIFICATION
# =====================================================================


def test_workspace_settings_model_defaults():
    """Verify exact model column defaults, types, and constraints on WorkspaceSettings."""
    table = WorkspaceSettings.__table__

    # Table name check
    assert table.name == "workspace_settings"

    # Column presence check
    cols = {c.name: c for c in table.columns}
    assert set(cols.keys()) == {
        "workspace_id",
        "default_invite_role",
        "invite_expiry_days",
        "activity_retention_days",
        "role_permissions",
        "created_at",
        "updated_at",
    }

    # Column 1: workspace_id
    c_wid = cols["workspace_id"]
    assert c_wid.primary_key is True
    assert c_wid.nullable is False
    assert isinstance(c_wid.type, PgUUID)
    assert c_wid.type.as_uuid is True

    # Foreign key check on workspace_id
    fk_list = list(c_wid.foreign_keys)
    assert len(fk_list) == 1
    fk = fk_list[0]
    assert fk._get_colspec() == "workspaces.id"
    assert fk.ondelete == "CASCADE"

    # Column 2: default_invite_role
    c_role = cols["default_invite_role"]
    assert c_role.nullable is False
    assert isinstance(c_role.type, String)
    assert c_role.type.length == 20
    assert c_role.default.arg == "member"

    # Column 3: invite_expiry_days
    c_expiry = cols["invite_expiry_days"]
    assert c_expiry.nullable is False
    assert isinstance(c_expiry.type, Integer)
    assert c_expiry.default.arg == 7

    # Column 4: activity_retention_days
    c_retention = cols["activity_retention_days"]
    assert c_retention.nullable is False
    assert isinstance(c_retention.type, Integer)
    assert c_retention.default.arg == 30

    # Column 5: role_permissions
    c_perms = cols["role_permissions"]
    assert c_perms.nullable is False
    assert isinstance(c_perms.type, JSONB)
    assert c_perms.default.arg is dict or c_perms.default.arg.__name__ == "dict"

    # Columns 6 & 7: timestamps
    c_created = cols["created_at"]
    c_updated = cols["updated_at"]
    assert c_created.nullable is False
    assert isinstance(c_created.type, DateTime)
    assert c_created.type.timezone is True
    assert c_updated.nullable is False
    assert isinstance(c_updated.type, DateTime)
    assert c_updated.type.timezone is True


# =====================================================================
# 2. MODEL INSTANTIATION & MUTABILITY ISOLATION
# =====================================================================


def test_instantiation_with_defaults():
    """Verify instantiating WorkspaceSettings with minimal arguments populates default values."""
    test_uuid = uuid.uuid4()
    ws = WorkspaceSettings(workspace_id=test_uuid)

    assert ws.workspace_id == test_uuid
    assert ws.default_invite_role == "member"
    assert ws.invite_expiry_days == 7
    assert ws.activity_retention_days == 30
    assert ws.role_permissions == {}


def test_instantiation_isolation():
    """Verify that multiple instances get distinct dictionary objects for role_permissions."""
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    ws1 = WorkspaceSettings(workspace_id=id1)
    ws2 = WorkspaceSettings(workspace_id=id2)

    assert ws1.role_permissions is not ws2.role_permissions

    # Mutating ws1 should not affect ws2
    ws1.role_permissions["admin"] = {"members.invite": False}
    assert ws1.role_permissions == {"admin": {"members.invite": False}}
    assert ws2.role_permissions == {}


def test_instantiation_with_custom_values():
    """Verify instantiating WorkspaceSettings with non-default values preserves kwargs."""
    test_uuid = uuid.uuid4()
    custom_perms = {
        "member": {"catalog.view": True, "members.invite": True},
        "admin": {"workspace.delete": False},
    }
    ws = WorkspaceSettings(
        workspace_id=test_uuid,
        default_invite_role="admin",
        invite_expiry_days=14,
        activity_retention_days=90,
        role_permissions=custom_perms,
    )

    assert ws.workspace_id == test_uuid
    assert ws.default_invite_role == "admin"
    assert ws.invite_expiry_days == 14
    assert ws.activity_retention_days == 90
    assert ws.role_permissions == custom_perms


# =====================================================================
# 3. JSON SERIALIZATION / DESERIALIZATION & MUTATION BEHAVIOR
# =====================================================================


class SQLiteWorkspaceSettings(SQLiteTestBase):
    __tablename__ = "test_ws_settings"

    workspace_id: Mapped[str] = mapped_column(String, primary_key=True)
    default_invite_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member"
    )
    invite_expiry_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    activity_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    role_permissions: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __init__(self, **kw):
        kw.setdefault("default_invite_role", "member")
        kw.setdefault("invite_expiry_days", 7)
        kw.setdefault("activity_retention_days", 30)
        kw.setdefault("role_permissions", {})
        super().__init__(**kw)


def test_sqlite_orm_json_serialization_and_mutation():
    """Verify ORM insert, retrieve, JSON serialization, and mutation tracking behavior."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLiteTestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    wid = str(uuid.uuid4())
    complex_permissions = {
        "admin": {
            "members.invite": True,
            "members.remove": False,
            "sub_config": {"nested_key": 123, "tags": ["alpha", "beta"]},
        },
        "member": {
            "queries.execute": True,
            "unicode_test": "🚀 BoloDB SQL",
        },
    }

    ws = SQLiteWorkspaceSettings(
        workspace_id=wid,
        default_invite_role="member",
        invite_expiry_days=7,
        activity_retention_days=30,
        role_permissions=complex_permissions,
    )

    session.add(ws)
    session.commit()

    # Query back from DB
    retrieved = session.execute(
        select(SQLiteWorkspaceSettings).where(
            SQLiteWorkspaceSettings.workspace_id == wid
        )
    ).scalar_one()

    assert retrieved.workspace_id == wid
    assert retrieved.default_invite_role == "member"
    assert retrieved.invite_expiry_days == 7
    assert retrieved.activity_retention_days == 30
    assert isinstance(retrieved.role_permissions, dict)
    assert retrieved.role_permissions == complex_permissions
    assert retrieved.role_permissions["admin"]["sub_config"]["tags"] == [
        "alpha",
        "beta",
    ]
    assert retrieved.role_permissions["member"]["unicode_test"] == "🚀 BoloDB SQL"

    # Empirical test: In-place mutation without re-assignment or flag_modified does NOT mark field dirty
    retrieved.role_permissions["member"]["queries.execute"] = False
    session.commit()
    # Re-fetch from DB in new session to verify DB content
    session.expire_all()
    unmodified_in_db = session.execute(
        select(SQLiteWorkspaceSettings).where(
            SQLiteWorkspaceSettings.workspace_id == wid
        )
    ).scalar_one()
    # In-place dict change without re-assignment leaves DB unchanged (True)
    assert unmodified_in_db.role_permissions["member"]["queries.execute"] is True

    # Empirical test: Explicit dictionary reassignment DOES mark field dirty and update DB
    updated_perms = dict(unmodified_in_db.role_permissions)
    updated_perms["member"] = dict(updated_perms["member"])
    updated_perms["member"]["queries.execute"] = False
    unmodified_in_db.role_permissions = updated_perms
    session.commit()

    session.expire_all()
    modified_in_db = session.execute(
        select(SQLiteWorkspaceSettings).where(
            SQLiteWorkspaceSettings.workspace_id == wid
        )
    ).scalar_one()
    assert modified_in_db.role_permissions["member"]["queries.execute"] is False

    session.close()


def test_postgresql_ddl_compilation():
    """Verify PostgreSQL DDL generation for WorkspaceSettings table."""
    engine = create_engine("postgresql://user:pass@localhost/db")
    table = WorkspaceSettings.__table__
    ddl = str(sa.schema.CreateTable(table).compile(engine))

    assert "CREATE TABLE workspace_settings" in ddl
    assert "workspace_id UUID NOT NULL" in ddl
    assert "default_invite_role VARCHAR(20) NOT NULL" in ddl
    assert "invite_expiry_days INTEGER NOT NULL" in ddl
    assert "activity_retention_days INTEGER NOT NULL" in ddl
    assert "role_permissions JSONB NOT NULL" in ddl
    assert "PRIMARY KEY (workspace_id)" in ddl
    assert (
        "FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE" in ddl
    )


# =====================================================================
# 4. ALEMBIC MIGRATION (e8f901a23b4c) VERIFICATION
# =====================================================================


def test_alembic_migration_metadata():
    """Verify revision metadata in Alembic migration file."""
    assert migration.revision == "e8f901a23b4c"
    assert migration.down_revision == "c1a4d7e29b58"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_alembic_migration_upgrade_and_downgrade(monkeypatch):
    """Empirically test upgrade() and downgrade() functions by intercepting op calls."""
    create_table_calls = []
    drop_table_calls = []

    def mock_create_table(name, *columns, **kwargs):
        create_table_calls.append((name, columns, kwargs))

    def mock_drop_table(name, **kwargs):
        drop_table_calls.append((name, kwargs))

    monkeypatch.setattr(migration.op, "create_table", mock_create_table)
    monkeypatch.setattr(migration.op, "drop_table", mock_drop_table)

    # Execute upgrade
    migration.upgrade()
    assert len(create_table_calls) == 1
    table_name, columns, kwargs = create_table_calls[0]
    assert table_name == "workspace_settings"

    # Extract column names and constraints
    col_dict = {}
    constraints = []
    for item in columns:
        if isinstance(item, sa.Column):
            col_dict[item.name] = item
        elif isinstance(item, (sa.ForeignKeyConstraint, sa.PrimaryKeyConstraint)):
            constraints.append(item)

    assert set(col_dict.keys()) == {
        "workspace_id",
        "default_invite_role",
        "invite_expiry_days",
        "activity_retention_days",
        "role_permissions",
        "created_at",
        "updated_at",
    }

    # Verify column definitions and server defaults
    wid_col = col_dict["workspace_id"]
    assert wid_col.nullable is False
    assert isinstance(wid_col.type, sa.UUID)

    role_col = col_dict["default_invite_role"]
    assert role_col.nullable is False
    assert isinstance(role_col.type, sa.String)
    assert role_col.type.length == 20
    assert role_col.server_default.arg == "member"

    expiry_col = col_dict["invite_expiry_days"]
    assert expiry_col.nullable is False
    assert isinstance(expiry_col.type, sa.Integer)
    assert expiry_col.server_default.arg == "7"

    retention_col = col_dict["activity_retention_days"]
    assert retention_col.nullable is False
    assert isinstance(retention_col.type, sa.Integer)
    assert retention_col.server_default.arg == "30"

    perms_col = col_dict["role_permissions"]
    assert perms_col.nullable is False
    assert isinstance(perms_col.type, postgresql.JSONB)
    assert perms_col.server_default.arg == "{}"

    created_col = col_dict["created_at"]
    assert created_col.nullable is False
    assert isinstance(created_col.type, sa.DateTime)
    assert created_col.type.timezone is True
    assert str(created_col.server_default.arg) == "now()"

    updated_col = col_dict["updated_at"]
    assert updated_col.nullable is False
    assert isinstance(updated_col.type, sa.DateTime)
    assert updated_col.type.timezone is True
    assert str(updated_col.server_default.arg) == "now()"

    # Verify constraints
    fk_constraints = [c for c in constraints if isinstance(c, sa.ForeignKeyConstraint)]
    pk_constraints = [c for c in constraints if isinstance(c, sa.PrimaryKeyConstraint)]

    assert len(fk_constraints) == 1
    fk = fk_constraints[0]
    assert fk.column_keys == ["workspace_id"]
    assert fk.ondelete == "CASCADE"

    assert len(pk_constraints) == 1
    pk = pk_constraints[0]
    pk_cols = list(pk._pending_colargs)
    assert pk_cols == ["workspace_id"]

    # Execute downgrade
    migration.downgrade()
    assert len(drop_table_calls) == 1
    assert drop_table_calls[0][0] == "workspace_settings"
