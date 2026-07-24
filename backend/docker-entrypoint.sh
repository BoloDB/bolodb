#!/bin/sh
# Bring the database schema up to date, then start the app.
#
# Point DATABASE_URL at a different database and the next deploy migrates it
# from wherever it is to the current head — a fresh database gets the whole
# history, an existing one gets only what it is missing. Without this the app
# starts happily against a stale schema and fails later, one endpoint at a
# time, wherever a missing table or column happens to be touched.
#
# Set RUN_MIGRATIONS=false to skip (e.g. a read-only replica, or when
# migrations are applied by a separate release step).
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  if [ -z "${DATABASE_URL}" ]; then
    echo "entrypoint: DATABASE_URL is not set — cannot migrate" >&2
    exit 1
  fi

  # A database that is still accepting connections gets a few chances; compose
  # brings services up together and the app usually wins the race.
  attempt=1
  max_attempts="${MIGRATION_MAX_ATTEMPTS:-10}"
  until (cd /app/backend && PYTHONPATH=/app alembic upgrade head); do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "entrypoint: migrations failed after ${attempt} attempts — refusing to start" >&2
      exit 1
    fi
    echo "entrypoint: migration attempt ${attempt}/${max_attempts} failed, retrying in 3s" >&2
    attempt=$((attempt + 1))
    sleep 3
  done
  echo "entrypoint: database schema is up to date"
fi

exec "$@"
