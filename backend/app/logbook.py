"""Per-query id minting.

This used to write a JSONL audit log under the config directory. The durable
record of every query and its feedback now lives in Postgres (`query_history`),
so nothing is written to disk here — the class survives only to hand each query
a short id that feedback is recorded against.
"""

import logging
import uuid

logger = logging.getLogger(__name__)


class SessionLog:
    def __init__(self, base_dir=None):
        # base_dir is accepted for backward compatibility and ignored — no files
        # are written.
        pass

    def log_query(self, db_id, question, result):
        """Return a short id for this query. Persistence is Postgres's job."""
        return uuid.uuid4().hex[:12]

    def log_feedback(self, query_id, verdict, reason=""):
        return None
