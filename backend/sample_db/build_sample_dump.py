"""Regenerate `webshop.dump.gz` from the upstream PostgreSQL sample database.

The sample store BoloDB ships is a trimmed copy of
https://github.com/JannikArndt/PostgreSQLSampleDatabase — a webshop with 1,000
customers, 1,000 products, ~17,700 articles and 2,000 orders. Upstream ships
`pg_dump` files that only Postgres can restore; BoloDB needs a zero-setup SQLite
file, so this script keeps the parts that carry data (the `COPY … FROM stdin`
blocks) and drops everything Postgres-specific around them.

Run it only when refreshing the vendored data:

    python backend/sample_db/build_sample_dump.py /path/to/PostgreSQLSampleDatabase

The output, `backend/sample_db/webshop.dump.gz`, is read at runtime by
`backend.sample_data.ensure_sample_db`.
"""

import gzip
import sys
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "webshop.dump.gz"

# Load order respects the foreign keys between tables.
SOURCES = [
    ("colors", "create.sql"),
    ("sizes", "create.sql"),
    ("labels", "labels.sql"),
    ("products", "products.sql"),
    ("articles", "articles.sql"),
    ("stock", "stock.sql"),
    ("customer", "customer.sql"),
    ("address", "address.sql"),
    ("order", "order.sql"),
    ("order_positions", "order_positions.sql"),
]

# `icon` is a bytea blob of brand logos — megabytes of hex that no question in a
# SQL demo ever asks about.
DROP_COLUMNS = {"labels": {"icon"}}


def _copy_block(text: str, table: str):
    """Return (columns, rows) for a table's `COPY … FROM stdin` block."""
    needle_variants = (
        f"COPY webshop.{table} (",
        f'COPY webshop."{table}" (',
    )
    for needle in needle_variants:
        start = text.find(needle)
        if start != -1:
            break
    else:
        raise SystemExit(f"No COPY block for {table}")

    header_end = text.index("\n", start)
    header = text[start:header_end]
    columns = [
        c.strip() for c in header[header.index("(") + 1 : header.rindex(")")].split(",")
    ]

    body = text[header_end + 1 :]
    body = body[: body.index("\n\\.")]
    rows = [line.split("\t") for line in body.split("\n") if line]
    return columns, rows


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    data_dir = Path(sys.argv[1]) / "data"

    cache: dict[str, str] = {}
    tables = []
    latest = None

    for table, filename in SOURCES:
        if filename not in cache:
            cache[filename] = (data_dir / filename).read_text(encoding="utf-8")
        columns, rows = _copy_block(cache[filename], table)

        drop = DROP_COLUMNS.get(table, set())
        keep = [i for i, c in enumerate(columns) if c not in drop]
        columns = [columns[i] for i in keep]
        rows = [[r[i] for i in keep] for r in rows]

        for row in rows:
            for value in row:
                stamp = _parse_timestamp(value)
                if stamp and (latest is None or stamp > latest):
                    latest = stamp

        tables.append((table, columns, rows))

    # The upstream data was generated in 2018. Left alone, every "last month"
    # or "this year" question against the demo returns nothing, which reads as a
    # broken product rather than old data. Slide the whole history forward so the
    # newest row lands on today, keeping every interval between rows intact.
    shift = timedelta(0)
    if latest is not None:
        shift = datetime.now().replace(microsecond=0) - latest

    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as fh:
        for table, columns, rows in tables:
            fh.write(f"COPY {table} ({', '.join(columns)}) FROM stdin;\n")
            for row in rows:
                fh.write("\t".join(_shift(v, shift) for v in row) + "\n")
            fh.write("\\.\n")

    total = sum(len(rows) for _, _, rows in tables)
    print(
        f"Wrote {OUT} — {len(tables)} tables, {total} rows, shifted by {shift.days} days"
    )


def _parse_timestamp(value: str):
    """Parse a pg_dump `timestamp with time zone` literal, or return None."""
    if len(value) < 19 or value[4] != "-" or value[7] != "-" or value[10] != " ":
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _shift(value: str, shift: timedelta) -> str:
    stamp = _parse_timestamp(value)
    if stamp is None:
        return value
    return (stamp + shift).strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    main()
