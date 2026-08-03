"""
Persists unrecoverable failed tasks to MongoDB `dead_letter` collection.
Documents can be inspected, replayed or discarded manually.
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import get_logger
from database.mongo import get_client

logger = get_logger(__name__)

COLLECTION = "dead_letter"


def record_dead_letter(
    task_name: str,
    task_id: str,
    args: list,
    kwargs: dict,
    exception: str,
    traceback: str,
) -> None:
    try:
        db = get_client()["radar_odio"]
        db[COLLECTION].insert_one({
            "task_name": task_name,
            "task_id":   task_id,
            "args":      args,
            "kwargs":    kwargs,
            "exception": exception,
            "traceback": traceback,
            "failed_at": datetime.now(timezone.utc),
        })
        logger.error(
            "dead_letter_recorded",
            task=task_name,
            task_id=task_id,
            exception=exception,
        )
    except Exception as exc:
        # Never let DLQ errors propagate
        logger.error("dead_letter_write_failed", error=str(exc))


def list_dead_letters(limit: int = 50) -> list[dict]:
    db = get_client()["radar_odio"]
    docs = list(db[COLLECTION].find({}, {"_id": 0}).sort("failed_at", -1).limit(limit))
    return docs


def replay_dead_letter(task_id: str) -> bool:
    """Re-send a dead-lettered task back to its original queue."""
    from tasks.app import app as celery_app

    db = get_client()["radar_odio"]
    doc = db[COLLECTION].find_one({"task_id": task_id})
    if not doc:
        return False

    celery_app.send_task(
        doc["task_name"],
        args=doc["args"],
        kwargs=doc["kwargs"],
    )
    db[COLLECTION].delete_one({"task_id": task_id})
    logger.info("dead_letter_replayed", task=doc["task_name"], task_id=task_id)
    return True
