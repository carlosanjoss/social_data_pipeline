from typing import Iterator

from config import settings, get_logger
from database.mongo import (
    get_posts_collection,
    get_comments_collection,
    upsert_many,
)

logger = get_logger(__name__)


def _batched(iterable: Iterator[dict], size: int) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def load_posts(docs: Iterator[dict], batch_size: int | None = None) -> dict[str, int]:
    size = batch_size or settings.batch_size
    collection = get_posts_collection()
    totals: dict[str, int] = {"inserted": 0, "modified": 0, "skipped": 0, "errors": 0}

    for batch in _batched(docs, size):
        counts = upsert_many(collection, batch)
        for k in totals:
            totals[k] += counts.get(k, 0)

    logger.info("load_posts_done", **totals)
    return totals


def load_comments(docs: Iterator[dict], batch_size: int | None = None) -> dict[str, int]:
    size = batch_size or settings.batch_size
    collection = get_comments_collection()
    totals: dict[str, int] = {"inserted": 0, "modified": 0, "skipped": 0, "errors": 0}

    for batch in _batched(docs, size):
        counts = upsert_many(collection, batch)
        for k in totals:
            totals[k] += counts.get(k, 0)

    logger.info("load_comments_done", **totals)
    return totals
