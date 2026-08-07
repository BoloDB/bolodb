"""A verification code must stop answering long before its space is explored.

Six digits is 10^6, a ten-minute window, and a correct guess returns session
cookies — so without a per-code attempt cap, guessing the code is a practical way
into an account rather than a theoretical one. The cap is counted on the code
itself, not per caller: an IP limit alone is worth little to anyone willing to
spread the guesses across addresses.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.pgdatabase import otp as otp_mod

USER_ID = "11111111-1111-1111-1111-111111111111"
GOOD = "123456"
BAD = "999999"


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeConn:
    """Answers the SELECT with a canned row and records every write."""

    def __init__(self, row):
        self._row = row
        self.writes = []

    async def execute(self, statement, *args):
        compiled = str(statement)
        if compiled.lstrip().upper().startswith("SELECT"):
            return _FakeResult(self._row)
        self.writes.append(_compiled_values(statement))
        return None


def _compiled_values(statement):
    """The column names an UPDATE sets, so a test can say which write happened."""
    try:
        return set(statement.compile().params) | {
            c.name for c in statement.table.columns if c.name in str(statement)
        }
    except Exception:
        return {str(statement)}


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def begin(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def _row(*, code=GOOD, attempts=0, expired=False):
    """One otp_codes row as verify_otp's SELECT returns it."""
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=-1 if expired else otp_mod.OTP_TTL_MINUTES
    )
    return (
        "otp-id",
        expires,
        hashlib.sha256(code.encode()).hexdigest(),
        attempts,
    )


@pytest.fixture
def conn(monkeypatch):
    """Installs a fake engine; the test sets `.row` before calling verify_otp."""
    holder = _FakeConn(None)
    monkeypatch.setattr(otp_mod, "get_engine", lambda: _FakeEngine(holder))
    return holder


@pytest.mark.asyncio
async def test_correct_code_is_accepted_and_spent(conn):
    conn._row = _row()
    assert await otp_mod.verify_otp(USER_ID, GOOD) is True
    assert any("used" in w for w in conn.writes), conn.writes


@pytest.mark.asyncio
async def test_wrong_code_is_rejected_and_counted(conn):
    conn._row = _row()
    assert await otp_mod.verify_otp(USER_ID, BAD) is False
    # The count is the whole point: a wrong guess used to select no row at all
    # (the query matched on the code hash), so there was nothing to count against
    # and a caller could guess forever.
    assert any("attempts" in w for w in conn.writes), conn.writes


@pytest.mark.asyncio
async def test_code_stops_answering_once_attempts_are_spent(conn):
    """Even the right code — the user has to request a fresh one."""
    conn._row = _row(attempts=otp_mod.MAX_OTP_ATTEMPTS)
    assert await otp_mod.verify_otp(USER_ID, GOOD) is False
    assert conn.writes == [], "an exhausted code must not be marked used"


@pytest.mark.asyncio
async def test_one_below_the_cap_still_works(conn):
    """Off-by-one guard: the cap must not spend the last legitimate try."""
    conn._row = _row(attempts=otp_mod.MAX_OTP_ATTEMPTS - 1)
    assert await otp_mod.verify_otp(USER_ID, GOOD) is True


@pytest.mark.asyncio
async def test_expired_code_is_rejected(conn):
    conn._row = _row(expired=True)
    assert await otp_mod.verify_otp(USER_ID, GOOD) is False


@pytest.mark.asyncio
async def test_missing_code_is_rejected(conn):
    conn._row = None
    assert await otp_mod.verify_otp(USER_ID, GOOD) is False


def test_the_cap_is_small_enough_to_matter():
    """A cap that lets through a meaningful share of 10^6 is not a cap.

    Pinned so nobody raises it to something comfortable without meaning to.
    """
    assert otp_mod.MAX_OTP_ATTEMPTS <= 10
    assert otp_mod.OTP_LENGTH >= 6
