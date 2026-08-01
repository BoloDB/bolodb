"""Tests for the cron expression engine behind scheduled queries.

The engine decides when reports fire, so the cases that matter are the ones
where a subtly wrong answer still looks plausible: the Vixie day-of-month /
day-of-week OR rule, month boundaries, and expressions that parse but never
occur.
"""

from datetime import datetime, timezone

import pytest

from backend.app.services import cron

# A Saturday, mid-morning.
BASE = datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc)


def _fmt(moments):
    return [m.strftime("%Y-%m-%d %H:%M") for m in moments]


def test_daily_expression_fires_at_the_named_hour():
    assert _fmt(cron.next_runs("0 9 * * *", 3, after=BASE)) == [
        "2026-08-02 09:00",
        "2026-08-03 09:00",
        "2026-08-04 09:00",
    ]


def test_time_later_today_is_not_skipped():
    """A slot still ahead of us today must fire today, not tomorrow."""
    assert _fmt(cron.next_runs("0 18 * * *", 1, after=BASE)) == ["2026-08-01 18:00"]


def test_next_run_is_strictly_after_the_reference_time():
    """Exactly-now must advance, or a claimed slot would re-fire forever."""
    exactly_nine = datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc)
    assert cron.next_run("0 9 * * *", after=exactly_nine) == datetime(
        2026, 8, 3, 9, 0, tzinfo=timezone.utc
    )


def test_hourly_and_stepped_minutes():
    assert _fmt(cron.next_runs("30 * * * *", 2, after=BASE)) == [
        "2026-08-01 11:30",
        "2026-08-01 12:30",
    ]
    assert _fmt(cron.next_runs("*/15 * * * *", 3, after=BASE)) == [
        "2026-08-01 10:45",
        "2026-08-01 11:00",
        "2026-08-01 11:15",
    ]


def test_weekday_names_and_ranges():
    assert _fmt(cron.next_runs("0 9 * * MON-FRI", 3, after=BASE)) == [
        "2026-08-03 09:00",
        "2026-08-04 09:00",
        "2026-08-05 09:00",
    ]
    # Numeric and named spellings must agree.
    assert cron.next_run("0 9 * * 1", after=BASE) == cron.next_run(
        "0 9 * * MON", after=BASE
    )


def test_sunday_is_both_zero_and_seven():
    assert cron.next_run("0 9 * * 0", after=BASE) == cron.next_run(
        "0 9 * * 7", after=BASE
    )


def test_monthly_crosses_the_month_boundary():
    assert _fmt(cron.next_runs("0 9 1 * *", 3, after=BASE)) == [
        "2026-09-01 09:00",
        "2026-10-01 09:00",
        "2026-11-01 09:00",
    ]


def test_day_of_month_and_weekday_are_ored_not_anded():
    """Vixie cron semantics: restricted dom *or* dow matches, not both.

    "0 9 1 * MON" is the 1st of the month and every Monday — an AND reading
    would fire far more rarely and be very hard to spot in production.
    """
    runs = _fmt(cron.next_runs("0 9 1 * MON", 4, after=BASE))
    assert runs == [
        "2026-08-03 09:00",  # Monday
        "2026-08-10 09:00",  # Monday
        "2026-08-17 09:00",  # Monday
        "2026-08-24 09:00",  # Monday
    ]
    # ...and the 1st still fires even though it is a Tuesday.
    september = cron.next_runs(
        "0 9 1 * MON", 1, after=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    )
    assert _fmt(september) == ["2026-09-01 09:00"]


def test_leap_day_is_reachable():
    """29 Feb must resolve to the next leap year rather than never matching."""
    upcoming = cron.next_run(
        "0 9 29 2 *", after=datetime(2026, 3, 1, tzinfo=timezone.utc)
    )
    assert upcoming == datetime(2028, 2, 29, 9, 0, tzinfo=timezone.utc)


def test_naive_datetimes_are_read_as_utc():
    naive = datetime(2026, 8, 1, 10, 30)
    assert cron.next_run("0 9 * * *", after=naive) == datetime(
        2026, 8, 2, 9, 0, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "0 9 * *",
        "0 9 * * * *",
        "99 9 * * *",
        "abc 9 * * *",
        "0 25 * * *",
        "0 9 * * */0",
        "5-1 9 * * *",
        "0 9 0 * *",
    ],
)
def test_invalid_expressions_are_rejected(expression):
    with pytest.raises(cron.CronError):
        cron.validate(expression)


def test_expression_that_never_occurs_is_rejected():
    """Parses fine, but 31 February never happens — refuse it at creation."""
    with pytest.raises(cron.CronError):
        cron.validate("0 9 31 2 *")


def test_validate_normalises_whitespace():
    assert cron.validate("  0   9  *  *  *  ") == "0 9 * * *"


class TestWindow:
    """starts_at / ends_at bound the firing times."""

    def test_starts_at_pushes_the_first_run_forward(self):
        runs = cron.next_runs(
            "0 9 * * *",
            2,
            after=BASE,
            starts_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        assert _fmt(runs) == ["2026-09-01 09:00", "2026-09-02 09:00"]

    def test_a_run_landing_exactly_on_starts_at_is_kept(self):
        runs = cron.next_runs(
            "0 9 * * *",
            1,
            after=BASE,
            starts_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
        )
        assert _fmt(runs) == ["2026-09-01 09:00"]

    def test_ends_at_closes_the_window(self):
        runs = cron.next_runs(
            "0 9 * * *",
            10,
            after=BASE,
            starts_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            ends_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
        )
        assert _fmt(runs) == [
            "2026-09-01 09:00",
            "2026-09-02 09:00",
            "2026-09-03 09:00",
        ]

    def test_a_fully_past_window_yields_nothing(self):
        assert (
            cron.next_run(
                "0 9 * * *",
                after=BASE,
                ends_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )
            is None
        )


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("0 9 * * *", "Daily at 09:00 UTC"),
        ("30 * * * *", "Hourly, at 30 past the hour"),
        ("*/15 * * * *", "Every 15 minutes"),
        ("* * * * *", "Every minute"),
        ("0 9 * * 1", "Every Monday at 09:00 UTC"),
        ("0 9 * * MON-FRI", "Every weekday at 09:00 UTC"),
        ("0 9 1 * *", "Monthly on day 1 at 09:00 UTC"),
        ("0 0 1 1 *", "Yearly on 1/1 at 00:00 UTC"),
        # Anything without a single clock time falls back to the raw form.
        ("0 9,17 * * *", "Cron: 0 9,17 * * *"),
    ],
)
def test_describe(expression, expected):
    assert cron.describe(expression) == expected


def test_describe_never_raises_on_bad_input():
    """The UI renders descriptions for stored rows; a bad one must not 500."""
    assert cron.describe("nonsense") == "nonsense"
