"""The sample webshop must load, join up, and read as current data.

The sample store is a trimmed copy of the PostgreSQL sample database at
https://github.com/JannikArndt/PostgreSQLSampleDatabase, replayed into SQLite by
`backend.sample_data`. It is the first thing a new user sees, so a broken load,
a mangled `money` column or dates stuck in 2018 all show up as the product being
wrong rather than the data being old.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from backend import sample_data

EXPECTED_ROWS = {
    "colors": 143,
    "sizes": 15,
    "labels": 1170,
    "products": 1000,
    "articles": 17730,
    "stock": 17730,
    "customers": 1000,
    "addresses": 1000,
    "orders": 2000,
    "order_positions": 5985,
}


@pytest.fixture(scope="module")
def sample_db(tmp_path_factory):
    """Build the sample database once, into a temp file, and open it."""
    path = tmp_path_factory.mktemp("sample") / "webshop.db"
    sample_data._build(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_every_table_loads_with_its_full_row_count(sample_db):
    counts = {
        table: sample_db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in EXPECTED_ROWS
    }
    assert counts == EXPECTED_ROWS


def test_reserved_and_singular_table_names_are_renamed(sample_db):
    """`order`/`customer`/`address` are hostile names to ask questions against."""
    names = {
        r[0]
        for r in sample_db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"orders", "customers", "addresses"} <= names
    assert not ({"order", "customer", "address"} & names)


def test_money_columns_load_as_numbers_not_dollar_strings(sample_db):
    """`$361.81` has to become 361.81, or every SUM() in the demo is a no-op."""
    row = sample_db.execute(
        "SELECT total, shippingcost FROM orders WHERE total IS NOT NULL LIMIT 1"
    ).fetchone()
    assert isinstance(row["total"], float)
    assert isinstance(row["shippingcost"], float)

    total = sample_db.execute("SELECT ROUND(SUM(total), 2) FROM orders").fetchone()[0]
    assert total > 0

    non_numeric = sample_db.execute(
        "SELECT COUNT(*) FROM orders WHERE typeof(total) NOT IN ('real', 'integer', 'null')"
    ).fetchone()[0]
    assert non_numeric == 0


def test_booleans_and_nulls_survive_the_copy_format(sample_db):
    actives = {
        r[0] for r in sample_db.execute("SELECT DISTINCT currentlyactive FROM articles")
    }
    assert actives <= {0, 1}
    assert 1 in actives, "some articles should be active"

    # `\N` in the dump means NULL, not the literal two characters.
    literal_nulls = sample_db.execute(
        "SELECT COUNT(*) FROM articles WHERE updated = '\\N'"
    ).fetchone()[0]
    assert literal_nulls == 0
    assert (
        sample_db.execute(
            "SELECT COUNT(*) FROM articles WHERE updated IS NULL"
        ).fetchone()[0]
        > 0
    )


def test_foreign_keys_all_resolve(sample_db):
    """Orphaned rows would make every JOIN in the demo silently drop data."""
    orphans = {
        "articles→products": "SELECT COUNT(*) FROM articles a LEFT JOIN products p ON p.id = a.productid WHERE p.id IS NULL",
        "order_positions→orders": "SELECT COUNT(*) FROM order_positions op LEFT JOIN orders o ON o.id = op.orderid WHERE o.id IS NULL",
        "order_positions→articles": "SELECT COUNT(*) FROM order_positions op LEFT JOIN articles a ON a.id = op.articleid WHERE a.id IS NULL",
        "orders→customers": "SELECT COUNT(*) FROM orders o LEFT JOIN customers c ON c.id = o.customerid WHERE c.id IS NULL",
        "stock→articles": "SELECT COUNT(*) FROM stock s LEFT JOIN articles a ON a.id = s.articleid WHERE a.id IS NULL",
    }
    found = {
        name: sample_db.execute(sql).fetchone()[0] for name, sql in orphans.items()
    }
    assert found == dict.fromkeys(orphans, 0)


def test_order_history_runs_up_to_the_present_day(sample_db):
    """Upstream's data stops in 2018; "last month" must still return rows."""
    newest = sample_db.execute("SELECT MAX(ordertimestamp) FROM orders").fetchone()[0]
    newest_dt = datetime.strptime(newest[:19], "%Y-%m-%d %H:%M:%S")
    assert datetime.now() - newest_dt < timedelta(days=2), (
        f"newest order is {newest} — sample data should end at today"
    )

    last_month = sample_db.execute(
        "SELECT COUNT(*) FROM orders WHERE ordertimestamp >= date('now', '-1 month')"
    ).fetchone()[0]
    assert last_month > 0, "a 'last month' question must have something to answer with"


def test_history_still_spans_years_after_being_shifted(sample_db):
    """Shifting must move the window, not compress it into a single day."""
    oldest, newest = sample_db.execute(
        "SELECT MIN(ordertimestamp), MAX(ordertimestamp) FROM orders"
    ).fetchone()
    span = datetime.strptime(newest[:19], "%Y-%m-%d %H:%M:%S") - datetime.strptime(
        oldest[:19], "%Y-%m-%d %H:%M:%S"
    )
    assert span > timedelta(days=365)


def test_dates_of_birth_are_left_alone(sample_db):
    """Only timestamps slide forward — shifting birthdays would invent infants."""
    newest_birth = sample_db.execute(
        "SELECT MAX(dateofbirth) FROM customers"
    ).fetchone()[0]
    assert newest_birth < "2010-01-01"


@pytest.mark.parametrize(
    "question,sql",
    [
        (
            "orders last month",
            "SELECT COUNT(*) AS orders_placed FROM orders "
            "WHERE ordertimestamp >= date('now','start of month','-1 month') "
            "AND ordertimestamp <  date('now','start of month')",
        ),
        (
            "revenue by category",
            "SELECT p.category, ROUND(SUM(op.amount * op.price), 2) AS revenue "
            "FROM order_positions op JOIN articles a ON a.id = op.articleid "
            "JOIN products p ON p.id = a.productid GROUP BY p.category ORDER BY revenue DESC",
        ),
        (
            "top customers by spend",
            "SELECT c.firstname || ' ' || c.lastname AS customer, ROUND(SUM(o.total), 2) AS total_spend "
            "FROM orders o JOIN customers c ON c.id = o.customerid "
            "GROUP BY c.id ORDER BY total_spend DESC LIMIT 10",
        ),
        (
            "out of stock articles",
            "SELECT a.id, a.description, s.count AS in_stock FROM articles a "
            "JOIN stock s ON s.articleid = a.id WHERE s.count = 0 AND a.currentlyactive = 1",
        ),
    ],
)
def test_seeded_starter_questions_return_rows(sample_db, question, sql):
    """The SQL seeded by `KnowledgeService.seed_sample` must run on this schema.

    These are shown as starter questions and used as verified examples, so SQL
    that no longer matches the schema would teach the model the wrong shape.
    """
    rows = sample_db.execute(sql).fetchall()
    assert rows, f"seeded query for {question!r} returned nothing"


def test_build_is_atomic(tmp_path, monkeypatch):
    """A failed build must not leave a half-loaded database for the next request."""
    target = tmp_path / "webshop.db"

    real_read_dump = sample_data._read_dump

    def exploding_dump():
        for i, block in enumerate(real_read_dump()):
            if i >= 2:
                raise RuntimeError("dump truncated")
            yield block

    monkeypatch.setattr(sample_data, "_read_dump", exploding_dump)

    with pytest.raises(RuntimeError):
        sample_data._build(target)

    assert not target.exists(), "a partial build must not be left in place"
    assert list(tmp_path.iterdir()) == [], "the temporary file must be cleaned up"
