from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
import os
import time
import uuid
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid7():
    try:
        return uuid.uuid7()
    except AttributeError:
        pass
    ts = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = rand >> 68
    rand_b = rand & ((1 << 62) - 1)
    return uuid.UUID(
        int=(ts << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    )


class Base(DeclarativeBase):
    pass


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"
