"""Standard 5-field cron parsing and next-run computation, evaluated in UTC.

Written by hand rather than pulling in croniter. The codebase deliberately keeps
its dependency surface small — raw httpx instead of the Resend SDK, a hand-rolled
uuid7 — and the slice of cron a reporting schedule needs is small enough to own
outright and test properly.

Supported syntax per field: ``*``, ``5``, ``1-5``, ``*/15``, ``1-20/3``, and
comma-separated lists of any of those. Month and weekday also accept three-letter
names (``JAN``, ``MON``). Weekday is 0-6 with Sunday as 0; 7 is accepted as a
second spelling of Sunday.

Day-of-month and day-of-week follow Vixie cron: when *both* are restricted the
day matches if *either* does, which is what makes "0 0 1 * MON" mean "the 1st and
every Monday" rather than "Mondays that fall on the 1st".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# A cron expression that never matches (29 Feb on a non-leap century, say) must
# terminate rather than spin. Eight years is well past any real reporting cadence
# and still covers the 4-year leap cycle twice over.
_MAX_SEARCH_DAYS = 366 * 8

_MONTH_NAMES = {
    name: i
    for i, name in enumerate(
        "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1
    )
}
_DAY_NAMES = {name: i for i, name in enumerate("SUN MON TUE WED THU FRI SAT".split())}


class CronError(ValueError):
    """Raised for an unparseable or out-of-range cron expression."""


class CronSchedule:
    """A parsed cron expression, ready to be asked for its next firing time."""

    __slots__ = (
        "expression",
        "minutes",
        "hours",
        "days",
        "months",
        "weekdays",
        "_dom_restricted",
        "_dow_restricted",
    )

    def __init__(self, expression: str):
        fields = expression.split()
        if len(fields) != 5:
            raise CronError(
                "A cron expression needs exactly 5 fields "
                "(minute hour day-of-month month day-of-week), "
                f"got {len(fields)}: {expression!r}"
            )
        minute, hour, dom, month, dow = fields

        self.expression = " ".join(fields)
        self.minutes = _parse_field(minute, 0, 59, "minute")
        self.hours = _parse_field(hour, 0, 23, "hour")
        self.days = _parse_field(dom, 1, 31, "day-of-month")
        self.months = _parse_field(month, 1, 12, "month", names=_MONTH_NAMES)
        self.weekdays = _parse_field(dow, 0, 7, "day-of-week", names=_DAY_NAMES)

        # 7 and 0 are both Sunday. Normalise so day matching only has to test 0.
        if 7 in self.weekdays:
            self.weekdays = (self.weekdays - {7}) | {0}

        self._dom_restricted = dom.strip() != "*"
        self._dow_restricted = dow.strip() != "*"

    def matches(self, moment: datetime) -> bool:
        """Whether ``moment`` (minute precision) is a firing time."""
        if moment.month not in self.months:
            return False
        if not self._day_matches(moment):
            return False
        return moment.hour in self.hours and moment.minute in self.minutes

    def _day_matches(self, moment: datetime) -> bool:
        # Python's weekday() is Monday=0; cron's is Sunday=0.
        dow = (moment.weekday() + 1) % 7
        dom_hit = moment.day in self.days
        dow_hit = dow in self.weekdays
        if self._dom_restricted and self._dow_restricted:
            return dom_hit or dow_hit
        if self._dom_restricted:
            return dom_hit
        if self._dow_restricted:
            return dow_hit
        return True

    def next_after(self, after: datetime) -> datetime | None:
        """First firing time strictly after ``after``, or None if it never fires.

        Naive datetimes are read as UTC; the result is always UTC-aware.
        """
        moment = _as_utc(after).replace(second=0, microsecond=0) + timedelta(minutes=1)

        sorted_hours = sorted(self.hours)
        sorted_minutes = sorted(self.minutes)
        day = moment.date()
        limit = day + timedelta(days=_MAX_SEARCH_DAYS)

        while day <= limit:
            probe = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            if probe.month in self.months and self._day_matches(probe):
                first_day = day == moment.date()
                for hour in sorted_hours:
                    if first_day and hour < moment.hour:
                        continue
                    for minute in sorted_minutes:
                        if first_day and hour == moment.hour and minute < moment.minute:
                            continue
                        return probe.replace(hour=hour, minute=minute)
            day += timedelta(days=1)
        return None

    def next_runs(self, count: int, after: datetime | None = None) -> list[datetime]:
        """The next ``count`` firing times, oldest first. Short if it stops firing."""
        cursor = _as_utc(after) if after else datetime.now(timezone.utc)
        out: list[datetime] = []
        for _ in range(max(0, count)):
            nxt = self.next_after(cursor)
            if nxt is None:
                break
            out.append(nxt)
            cursor = nxt
        return out


def _as_utc(moment: datetime) -> datetime:
    return (
        moment.replace(tzinfo=timezone.utc)
        if moment.tzinfo is None
        else moment.astimezone(timezone.utc)
    )


def _parse_field(
    raw: str,
    low: int,
    high: int,
    label: str,
    names: dict[str, int] | None = None,
) -> set[int]:
    raw = raw.strip()
    if not raw:
        raise CronError(f"Empty {label} field")

    values: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"Empty entry in {label} field: {raw!r}")

        step = 1
        if "/" in part:
            part, _, step_raw = part.partition("/")
            part = part.strip()
            try:
                step = int(step_raw)
            except ValueError:
                raise CronError(
                    f"Step in {label} field must be a whole number, got {step_raw!r}"
                ) from None
            if step < 1:
                raise CronError(f"Step in {label} field must be 1 or more, got {step}")

        if part == "*":
            start, end = low, high
        elif "-" in part:
            start_raw, _, end_raw = part.partition("-")
            start = _parse_value(start_raw, low, high, label, names)
            end = _parse_value(end_raw, low, high, label, names)
            if start > end:
                raise CronError(f"Range in {label} field runs backwards: {part!r}")
        else:
            start = _parse_value(part, low, high, label, names)
            # A bare value with a step means "from here to the end of the field"
            # (`5/10` in the hour field is 5, 15). Without a step it's just itself.
            end = high if step > 1 else start

        values.update(range(start, end + 1, step))

    if not values:
        raise CronError(f"{label} field matches nothing: {raw!r}")
    return values


def _parse_value(
    raw: str, low: int, high: int, label: str, names: dict[str, int] | None
) -> int:
    token = raw.strip()
    if not token:
        raise CronError(f"Empty value in {label} field")
    if names:
        named = names.get(token.upper())
        if named is not None:
            return named
    try:
        value = int(token)
    except ValueError:
        raise CronError(f"Unrecognised {label} value: {token!r}") from None
    if not low <= value <= high:
        raise CronError(f"{label} value {value} is outside {low}-{high}")
    return value


def parse(expression: str) -> CronSchedule:
    """Parse a cron expression, raising CronError if it is not usable."""
    if not isinstance(expression, str) or not expression.strip():
        raise CronError("Cron expression is required")
    return CronSchedule(expression.strip())


def validate(expression: str) -> str:
    """Return the normalised expression, raising CronError if invalid.

    Also rejects expressions that parse but can never fire (``0 0 31 2 *``),
    which would otherwise create a schedule that silently never runs.
    """
    schedule = parse(expression)
    if schedule.next_after(datetime.now(timezone.utc)) is None:
        raise CronError(
            f"{expression!r} is a valid expression but never occurs — "
            "check the day-of-month and month combination"
        )
    return schedule.expression


def next_run(
    expression: str,
    after: datetime | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> datetime | None:
    """Next firing time inside the schedule's active window.

    ``starts_at`` pushes the search forward so a schedule created today can be
    told not to fire until next month; ``ends_at`` closes it off, returning None
    once the window has passed so the caller can retire the schedule.
    """
    cursor = _as_utc(after) if after else datetime.now(timezone.utc)
    if starts_at is not None:
        begin = _as_utc(starts_at)
        # Stepping back a minute keeps a firing time landing exactly on
        # starts_at eligible, since next_after is strictly-after.
        if begin > cursor:
            cursor = begin - timedelta(minutes=1)

    upcoming = parse(expression).next_after(cursor)
    if upcoming is None:
        return None
    if ends_at is not None and upcoming > _as_utc(ends_at):
        return None
    return upcoming


def next_runs(
    expression: str,
    count: int = 5,
    after: datetime | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> list[datetime]:
    """Preview the next ``count`` firing times inside the active window."""
    cursor = _as_utc(after) if after else datetime.now(timezone.utc)
    out: list[datetime] = []
    for _ in range(max(0, count)):
        upcoming = next_run(
            expression, after=cursor, starts_at=starts_at, ends_at=ends_at
        )
        if upcoming is None:
            break
        out.append(upcoming)
        cursor = upcoming
    return out


_DAY_LABELS = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}


def describe(expression: str) -> str:
    """A short human-readable summary, for schedule lists and email footers.

    Covers the shapes the UI's presets generate and falls back to the raw
    expression for anything hand-written and exotic.
    """
    try:
        schedule = parse(expression)
    except CronError:
        return expression

    minute, hour, dom, month, dow = schedule.expression.split()

    if minute == "*" and hour == "*":
        return "Every minute"

    if (
        minute.startswith("*/")
        and minute[2:].isdigit()
        and hour == "*"
        and dom == "*"
        and month == "*"
        and dow == "*"
    ):
        return f"Every {int(minute[2:])} minutes"

    # Everything below reads a single clock time out of the expression, so any
    # minute or hour that stands for more than one value (a list, range or step)
    # has no "at HH:MM" to describe and falls through to the raw form.
    if not minute.isdigit():
        return f"Cron: {schedule.expression}"

    if hour == "*" and dom == "*" and month == "*" and dow == "*":
        return f"Hourly, at {int(minute):02d} past the hour"

    if not hour.isdigit():
        return f"Cron: {schedule.expression}"

    at = f"{int(hour):02d}:{int(minute):02d} UTC"

    if dom == "*" and month == "*" and dow == "*":
        return f"Daily at {at}"

    if dom == "*" and month == "*" and dow != "*":
        days = sorted(schedule.weekdays)
        if days == [1, 2, 3, 4, 5]:
            return f"Every weekday at {at}"
        labels = ", ".join(_DAY_LABELS[d] for d in days)
        return f"Every {labels} at {at}"

    if dom != "*" and dow == "*" and month == "*" and dom.isdigit():
        return f"Monthly on day {int(dom)} at {at}"

    if dom != "*" and dow == "*" and month != "*" and dom.isdigit() and month.isdigit():
        return f"Yearly on {int(dom)}/{int(month)} at {at}"

    return f"Cron: {schedule.expression}"
