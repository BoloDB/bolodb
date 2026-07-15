"""Local session logging for validation."""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5


class SessionLog:
    def __init__(self, base_dir):
        self.dir = Path(base_dir) / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.file = self.dir / f"session-{stamp}.jsonl"
        self._setup_rotating_handler()

    def _setup_rotating_handler(self):
        self._handler = RotatingFileHandler(
            str(self.file),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )

    def _append(self, record):
        record.update(
            {
                "ts": time.time(),
                "ts_human": datetime.now().isoformat(timespec="seconds"),
            }
        )
        try:
            line = json.dumps(record, default=str) + "\n"
            self._handler.stream = open(self.file, "a", encoding="utf-8")
            self._handler.emit(
                logging.LogRecord(
                    name=__name__,
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=line,
                    args=(),
                    exc_info=None,
                )
            )
            self._handler.stream.close()
        except Exception as e:
            logger.error("Failed to append to session log: %s", e)

    def log_query(self, db_id, question, result):
        import uuid

        qid = uuid.uuid4().hex[:12]
        self._append(
            {
                "event": "query",
                "query_id": qid,
                "db_id": db_id,
                "question": question,
                "sql": result.get("sql"),
                "confidence": result.get("confidence"),
                "confidence_reason": result.get("confidence_reason"),
                "based_on_verified": result.get("based_on_verified"),
                "row_count": len(result.get("rows", []) or []),
                "execution_error": result.get("execution_error"),
                # Audit trail for linking quality: exactly which tables the AI
                # was shown (including schema-retry additions) and how many
                # generation attempts the repair loop needed.
                "tables_used": result.get("tables_used"),
                "attempts": result.get("attempts"),
            }
        )
        return qid

    def log_feedback(self, query_id, verdict, reason=""):
        self._append(
            {
                "event": "feedback",
                "query_id": query_id,
                "verdict": verdict,
                "reason": reason,
            }
        )
