"""Builds the sample webshop database on first run.

The data is a trimmed copy of the PostgreSQL sample database at
https://github.com/JannikArndt/PostgreSQLSampleDatabase — a webshop with 1,000
customers, 1,000 products across ~17,700 articles, and 2,000 orders with their
positions. Upstream ships `pg_dump` output; `backend/sample_db/webshop.dump.gz`
holds just the `COPY … FROM stdin` blocks from it (see
`backend/sample_db/build_sample_dump.py`), which this module replays into a
local SQLite file so trying the sample needs no database of your own.
"""

import gzip
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DUMP_PATH = Path(__file__).parent / "sample_db" / "webshop.dump.gz"

# Bumped whenever the schema or data changes, so an existing sample file from an
# older release is rebuilt instead of silently serving the previous dataset.
SAMPLE_VERSION = 2

SCHEMA = """
CREATE TABLE colors (
  id   INTEGER PRIMARY KEY,
  name TEXT,
  rgb  TEXT
);

CREATE TABLE sizes (
  id       INTEGER PRIMARY KEY,
  gender   TEXT,
  category TEXT,
  size     TEXT,
  size_us  TEXT,
  size_uk  TEXT,
  size_eu  TEXT
);

CREATE TABLE labels (
  id       INTEGER PRIMARY KEY,
  name     TEXT,
  slugname TEXT
);

CREATE TABLE products (
  id              INTEGER PRIMARY KEY,
  name            TEXT,
  labelid         INTEGER REFERENCES labels (id),
  category        TEXT,
  gender          TEXT,
  currentlyactive INTEGER,
  created         TEXT,
  updated         TEXT
);

CREATE TABLE articles (
  id                INTEGER PRIMARY KEY,
  productid         INTEGER REFERENCES products (id),
  ean               TEXT,
  colorid           INTEGER REFERENCES colors (id),
  sizeid            INTEGER REFERENCES sizes (id),
  description       TEXT,
  originalprice     REAL,
  reducedprice      REAL,
  taxrate           REAL,
  discountinpercent INTEGER,
  currentlyactive   INTEGER,
  created           TEXT,
  updated           TEXT
);

CREATE TABLE stock (
  id        INTEGER PRIMARY KEY,
  articleid INTEGER REFERENCES articles (id),
  count     INTEGER,
  created   TEXT,
  updated   TEXT
);

CREATE TABLE customers (
  id               INTEGER PRIMARY KEY,
  firstname        TEXT,
  lastname         TEXT,
  gender           TEXT,
  email            TEXT,
  dateofbirth      TEXT,
  currentaddressid INTEGER,
  created          TEXT,
  updated          TEXT
);

CREATE TABLE addresses (
  id         INTEGER PRIMARY KEY,
  customerid INTEGER REFERENCES customers (id),
  firstname  TEXT,
  lastname   TEXT,
  address1   TEXT,
  address2   TEXT,
  city       TEXT,
  zip        TEXT,
  created    TEXT,
  updated    TEXT
);

CREATE TABLE orders (
  id                INTEGER PRIMARY KEY,
  customerid        INTEGER REFERENCES customers (id),
  ordertimestamp    TEXT,
  shippingaddressid INTEGER REFERENCES addresses (id),
  total             REAL,
  shippingcost      REAL,
  created           TEXT,
  updated           TEXT
);

CREATE TABLE order_positions (
  id        INTEGER PRIMARY KEY,
  orderid   INTEGER REFERENCES orders (id),
  articleid INTEGER REFERENCES articles (id),
  amount    INTEGER,
  price     REAL,
  created   TEXT,
  updated   TEXT
);

CREATE INDEX idx_articles_product ON articles (productid);
CREATE INDEX idx_stock_article ON stock (articleid);
CREATE INDEX idx_orders_customer ON orders (customerid);
CREATE INDEX idx_order_positions_order ON order_positions (orderid);
CREATE INDEX idx_order_positions_article ON order_positions (articleid);
"""

# `order` and `customer` are awkward names to ask questions against — one is a
# SQL reserved word, the other reads as a single row — so both are pluralised
# on the way in. `size` and `customer` become `sizeid`/`customerid` to match the
# foreign keys they actually are (upstream's own CREATE scripts name them so).
TABLE_NAMES = {"order": "orders", "customer": "customers", "address": "addresses"}
COLUMN_NAMES = {
    "articles": {"size": "sizeid"},
    "order": {"customer": "customerid"},
}

# Everything not listed loads as text.
COLUMN_TYPES = {
    "id": "int",
    "labelid": "int",
    "productid": "int",
    "colorid": "int",
    "sizeid": "int",
    "articleid": "int",
    "orderid": "int",
    "customerid": "int",
    "currentaddressid": "int",
    "shippingaddressid": "int",
    "count": "int",
    "amount": "int",
    "discountinpercent": "int",
    "taxrate": "real",
    "originalprice": "money",
    "reducedprice": "money",
    "price": "money",
    "total": "money",
    "shippingcost": "money",
    "currentlyactive": "bool",
}

# pg_dump escapes these inside COPY text fields.
_UNESCAPE = {"\\t": "\t", "\\n": "\n", "\\r": "\r", "\\\\": "\\"}


# The generated SQLite file lives in the repo's data/ directory, not a user
# home or a persistent volume. It is a cache rebuilt from the vendored dump, so
# it can be thrown away and regenerated at any time. Overridable for tests.
_DATA_DIR = Path(
    os.environ.get("BOLODB_DATA_DIR", Path(__file__).resolve().parent.parent / "data")
)


def sample_db_path() -> Path:
    return _DATA_DIR / f"sample_webshop_v{SAMPLE_VERSION}.db"


def ensure_sample_db() -> str:
    """Return a connection URL for the sample database, building it if needed."""
    path = sample_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _build(path)
        _remove_stale_samples(path)
    return f"sqlite:///{path.as_posix()}"


def _build(path: Path) -> None:
    """Load the vendored dump into a fresh SQLite file at `path`.

    Built into a temporary file in the same directory and moved into place, so a
    build that dies halfway (or two workers racing on first connect) can never
    leave a half-loaded database behind for the next request to read.
    """
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".db")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        conn = sqlite3.connect(str(tmp))
        try:
            conn.executescript(SCHEMA)
            for table, columns, rows in _read_dump():
                placeholders = ", ".join("?" * len(columns))
                quoted = ", ".join(f'"{c}"' for c in columns)
                conn.executemany(
                    f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})', rows
                )
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp, path)
        logger.info("Sample database created: %s", path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _remove_stale_samples(current: Path) -> None:
    """Delete sample files left by earlier versions of the sample dataset."""
    for old in current.parent.glob("sample_*.db"):
        if old != current:
            try:
                old.unlink()
            except OSError as e:
                logger.warning("Could not remove old sample database %s: %s", old, e)


def _read_dump():
    """Yield (table, columns, rows) for each COPY block in the vendored dump."""
    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as fh:
        table = None
        columns: list[str] = []
        converters: list[str] = []
        rows: list[tuple] = []
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("COPY "):
                header = line[len("COPY ") :]
                source_table = header[: header.index(" (")].strip()
                source_columns = [
                    c.strip()
                    for c in header[header.index("(") + 1 : header.rindex(")")].split(
                        ","
                    )
                ]
                renames = COLUMN_NAMES.get(source_table, {})
                table = TABLE_NAMES.get(source_table, source_table)
                columns = [renames.get(c, c) for c in source_columns]
                converters = [COLUMN_TYPES.get(c, "text") for c in columns]
                rows = []
            elif line == "\\.":
                yield table, columns, rows
                table = None
            elif table is not None:
                values = line.split("\t")
                rows.append(
                    tuple(
                        _convert(v, t) for v, t in zip(values, converters, strict=True)
                    )
                )


def _convert(value: str, kind: str):
    if value == "\\N":
        return None
    if kind == "text":
        return _unescape(value)
    if kind == "bool":
        return 1 if value == "t" else 0
    if kind == "int":
        return int(value)
    if kind == "money":
        # pg's `money` type dumps as `$1,234.56`, negatives as `-$1,234.56`.
        cleaned = value.replace("$", "").replace(",", "")
        return float(cleaned) if cleaned else None
    return float(value)


def _unescape(value: str) -> str:
    if "\\" not in value:
        return value
    out = []
    i = 0
    while i < len(value):
        pair = value[i : i + 2]
        if pair in _UNESCAPE:
            out.append(_UNESCAPE[pair])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


if __name__ == "__main__":
    print(ensure_sample_db())
