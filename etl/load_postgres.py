"""
Reads raw_posts / raw_comments from MongoDB, normalizes each document,
and upserts into PostgreSQL (posts + extension tables, comments + extension tables).

Only records in Brazilian Portuguese are loaded. There is no date restriction.
Batch size comes from settings.batch_size.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from psycopg import Connection

from config import settings, get_logger
from database.mongo import get_posts_collection, get_comments_collection
from normalizers import normalize_post, normalize_comment
from repositories.posts import upsert_posts
from repositories.comments import upsert_comments
from services.language import is_pt_br

logger = get_logger(__name__)

BATCH = settings.batch_size

TARGET_LANGUAGE = settings.target_language


def _is_target_language(base: dict, *text_parts: object) -> bool:
    """Rejeita metadado explicitamente não português e confirma pelo texto."""
    declared = str(base.get("language") or "").strip().lower().replace("_", "-")
    if declared and declared not in {"pt", "pt-br"}:
        return False
    if base.get("language_verified") and declared in {"pt", "pt-br"}:
        return True
    return is_pt_br(*text_parts)


@dataclass
class LoadResult:
    platform: str
    collection: str
    inserted: int = 0
    modified: int = 0
    errors: int = 0
    skipped_language: int = 0
    elapsed_s: float = 0.0
    error_samples: list[str] = field(default_factory=list)


def _load_posts(conn: Connection, platform: str) -> LoadResult:
    result = LoadResult(platform=platform, collection="posts")
    t0 = time.perf_counter()
    coll = get_posts_collection()

    batch: list[tuple[dict, dict]] = []

    for doc in coll.find({"platform": platform}, batch_size=BATCH):
        try:
            base, ext = normalize_post(doc)
        except Exception as exc:
            result.errors += 1
            result.error_samples.append(str(exc)[:120])
            continue

        if not _is_target_language(base, base.get("title"), base.get("text")):
            result.skipped_language += 1
            continue

        base["language"] = TARGET_LANGUAGE

        batch.append((base, ext))

        if len(batch) >= BATCH:
            counts = upsert_posts(conn, batch, platform)
            result.inserted += counts["inserted"]
            result.modified  += counts["modified"]
            batch.clear()

    if batch:
        counts = upsert_posts(conn, batch, platform)
        result.inserted += counts["inserted"]
        result.modified  += counts["modified"]

    result.elapsed_s = time.perf_counter() - t0
    logger.info(
        "load_posts_done",
        platform=platform,
        inserted=result.inserted,
        modified=result.modified,
        errors=result.errors,
        skipped_language=result.skipped_language,
        elapsed_s=round(result.elapsed_s, 2),
    )
    return result


def _load_comments(conn: Connection, platform: str) -> LoadResult:
    result = LoadResult(platform=platform, collection="comments")
    t0 = time.perf_counter()
    coll = get_comments_collection()

    batch: list[tuple[dict, dict]] = []

    for doc in coll.find({"platform": platform}, batch_size=BATCH):
        try:
            base, ext = normalize_comment(doc)
        except Exception as exc:
            result.errors += 1
            result.error_samples.append(str(exc)[:120])
            continue

        if not _is_target_language(base, base.get("text")):
            result.skipped_language += 1
            continue

        base["language"] = TARGET_LANGUAGE

        batch.append((base, ext))

        if len(batch) >= BATCH:
            counts = upsert_comments(conn, batch, platform)
            result.inserted += counts["inserted"]
            result.modified  += counts["modified"]
            batch.clear()

    if batch:
        counts = upsert_comments(conn, batch, platform)
        result.inserted += counts["inserted"]
        result.modified  += counts["modified"]

    result.elapsed_s = time.perf_counter() - t0
    logger.info(
        "load_comments_done",
        platform=platform,
        inserted=result.inserted,
        modified=result.modified,
        errors=result.errors,
        skipped_language=result.skipped_language,
        elapsed_s=round(result.elapsed_s, 2),
    )
    return result


def run_load(
    conn: Connection,
    platforms: list[str] | None = None,
) -> list[LoadResult]:
    all_platforms = [
        "reddit", "twitter", "youtube", "facebook", "tiktok",
        "whatsapp", "telegram",
    ]
    targets = platforms or all_platforms
    results: list[LoadResult] = []

    for platform in targets:
        logger.info("load_platform_start", platform=platform)
        results.append(_load_posts(conn, platform))
        results.append(_load_comments(conn, platform))

    return results
