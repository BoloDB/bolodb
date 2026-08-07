"""Runtime configuration, held in memory only.

BoloDB keeps no local state on disk. Secrets come from the environment, and
everything a user creates lives in Postgres. The only file the app writes is the
sample database, and that is a regenerable cache under the repo's ``data/``
directory (see ``backend/sample_data.py``), not configuration.

``cfg`` is a small per-process dict: the OpenRouter key (always read fresh from
the environment) and the last connected database URL (a convenience value that
lives only for the process lifetime). Nothing here is persisted.
"""

import logging
import os

log = logging.getLogger(__name__)


def _env_number(name, default, cast, minimum=None):
    """Read a numeric env var without ever crashing process startup.

    A malformed value (e.g. ``ACTIVITY_CLEANUP_INTERVAL_HOURS=daily``) must not
    abort import and take every route down with it — fall back to the default
    and warn. ``minimum`` clamps the result so a misconfigured 0/negative
    interval can't turn the cleanup loop into a busy loop.
    """
    raw = os.environ.get(name)
    if raw is None:
        value = cast(default)
    else:
        try:
            value = cast(raw)
        except (TypeError, ValueError):
            log.warning("Invalid %s=%r; falling back to default %r", name, raw, default)
            value = cast(default)
    if minimum is not None:
        value = max(minimum, value)
    return value


ACTIVITY_LOG_RETENTION_DAYS = _env_number(
    "ACTIVITY_LOG_RETENTION_DAYS", 30, int, minimum=1
)
# Periodic pruning of activity rows past the retention window. Safe to run
# in-process because BoloDB is deployed single-process; set the flag to "false"
# if that ever stops being true and the job moves to a dedicated worker.
ACTIVITY_CLEANUP_ENABLED = os.environ.get(
    "ACTIVITY_CLEANUP_ENABLED", "true"
).lower() not in ("false", "0", "no")
ACTIVITY_CLEANUP_INTERVAL_HOURS = _env_number(
    "ACTIVITY_CLEANUP_INTERVAL_HOURS", 24, float, minimum=0.1
)

# ── Scheduled queries ───────────────────────────────────────────────
# Same single-process caveat as the cleanup loop above, but with sharper teeth:
# a duplicated cleanup pass is invisible, a duplicated report is already in
# someone's inbox. The scheduler guards against that with a compare-and-swap on
# next_run_at, so a second process would contend rather than double-send — but
# the flag is the clean way to turn it off if the job ever moves to a worker.
SCHEDULED_QUERIES_ENABLED = os.environ.get(
    "SCHEDULED_QUERIES_ENABLED", "true"
).lower() not in ("false", "0", "no")
# How often to look for due schedules. Cron resolves to the minute, so polling
# faster than that buys nothing.
SCHEDULER_TICK_SECONDS = _env_number("SCHEDULER_TICK_SECONDS", 60, float, minimum=5)
# A report query gets longer than an interactive one — nobody is waiting on it —
# but not unbounded, or one pathological query stalls every other schedule.
SCHEDULE_QUERY_TIMEOUT_SECONDS = _env_number(
    "SCHEDULE_QUERY_TIMEOUT_SECONDS", 300, float, minimum=10
)
# Reports run against customer databases that are also serving live traffic.
SCHEDULE_MAX_CONCURRENT = _env_number("SCHEDULE_MAX_CONCURRENT", 4, int, minimum=1)
# Consecutive failures before a schedule pauses itself and emails the owner.
SCHEDULE_MAX_FAILURES = _env_number("SCHEDULE_MAX_FAILURES", 5, int, minimum=1)
# How late a run may fire after its slot. Past this the occurrence is recorded as
# skipped instead — a restart after a long outage should not deliver yesterday's
# 9am report at 3pm today.
SCHEDULE_MISFIRE_GRACE_SECONDS = _env_number(
    "SCHEDULE_MISFIRE_GRACE_SECONDS", 3600, float, minimum=60
)

DEFAULTS = {
    "openrouter_key": "",
}


def default_config():
    return dict(DEFAULTS)


def load_config():
    """Build the in-memory config from the environment. Reads no files."""
    cfg = default_config()
    # The API key is always read fresh from the environment, never stored.
    cfg["openrouter_key"] = os.environ.get("OPENROUTER_API_KEY", "")
    return cfg


def public_config(cfg):
    """Config as exposed to the frontend — never includes the API key.

    Empty today. Kept as a function, and as a key in the state payload, so the
    shape the frontend already receives does not change and there is somewhere
    obvious to put the next publicly-safe setting.
    """
    return {}
