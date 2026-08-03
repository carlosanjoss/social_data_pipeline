from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import BulkWriteError
from pymongo import UpdateOne

from config import get_logger

logger = get_logger(__name__)


def upsert_one(collection: Collection, document: dict[str, Any]) -> str:
    """Insert or update a document keyed by (platform, external_id). Returns 'inserted' | 'updated' | 'skipped'."""
    filter_ = {
        "platform":    document["platform"],
        "external_id": document["external_id"],
    }
    document.setdefault("collected_at", datetime.now(timezone.utc))
    result = collection.update_one(
        filter_,
        {"$set": document},
        upsert=True,
    )
    if result.upserted_id:
        return "inserted"
    if result.modified_count:
        return "updated"
    return "skipped"


def upsert_many(collection: Collection, documents: list[dict[str, Any]]) -> dict[str, int]:
    """Bulk upsert. Returns counts: inserted, modified, skipped."""
    if not documents:
        return {"inserted": 0, "modified": 0, "skipped": 0, "errors": 0}

    now = datetime.now(timezone.utc)
    ops = [
        UpdateOne(
            {"platform": doc["platform"], "external_id": doc["external_id"]},
            {"$set": {**doc, "collected_at": doc.get("collected_at", now)}},
            upsert=True,
        )
        for doc in documents
    ]

    try:
        result = collection.bulk_write(ops, ordered=False)
        skipped = len(documents) - result.upserted_count - result.modified_count
        counts = {
            "inserted": result.upserted_count,
            "modified": result.modified_count,
            "skipped":  max(skipped, 0),
            "errors":   0,
        }
    except BulkWriteError as exc:
        write_errors = exc.details.get("writeErrors", [])
        counts = {
            "inserted": exc.details.get("nUpserted", 0),
            "modified": exc.details.get("nModified", 0),
            "skipped":  0,
            "errors":   len(write_errors),
        }
        logger.error("bulk_write_errors", count=len(write_errors), sample=write_errors[:3])

    logger.debug(
        "upsert_many_done",
        collection=collection.name,
        total=len(documents),
        **counts,
    )
    return counts
