"""Local session logging for validation."""

import json
import time
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionLog:
    def __init__(self, base_dir):
        self.dir = Path(base_dir) / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.file = self.dir / f"session-{stamp}.jsonl"

    def _append(self, record):
        record.update(
            {
                "ts": time.time(),
                "ts_human": datetime.now().isoformat(timespec="seconds"),
            }
        )
        try:
            with open(self.file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
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
