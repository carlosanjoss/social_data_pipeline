"""
Reads raw_posts / raw_comments from MongoDB, normalizes each document,
and upserts into PostgreSQL (posts + extension tables, comments + extension tables).

Only records in Brazilian Portuguese are loaded. There is no date restriction.
Batch size comes from settings.batch_size.

A deteccao de idioma (langdetect, CPU-bound) roda em pool de processos. Com
``decide_target`` fixado em services.language o resultado e identico ao modo
sequencial, apenas muito mais rapido em corpora grandes.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

from psycopg import Connection

from config import settings, get_logger
from database.mongo import get_posts_collection, get_comments_collection
from normalizers import normalize_post, normalize_comment
from repositories.posts import upsert_posts
from repositories.comments import upsert_comments, resolve_post_fks
from services.language import decide_target, decide_target_payload, decide_batch, detect_language_robust

logger = get_logger(__name__)

BATCH = settings.batch_size

TARGET_LANGUAGE = settings.target_language

# Quantos documentos paralelizar por chamada ao pool.
CHUNK = 20_000

# Itens por tarefa enviada a um worker (menos overhead de pickling).
SLICE = 2_000

# Campos textuais considerados na detecção de idioma, por coleção.
_PARTS_POST = ("title", "text")
_PARTS_COMMENT = ("text",)

# Quantos posts-âncora buscar de uma vez no Mongo.
_MONGO_LOOKUP_CHUNK = 1_000


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


def _is_target_language(base: dict, *text_parts: object) -> bool:
    """Compat: decisao de fronteira sequencial (usada por testes)."""
    return decide_target(
        base.get("language"),
        bool(base.get("language_verified")),
        tuple(text_parts),
    )


def _payload(base: dict, parts: tuple) -> tuple:
    return (
        base.get("language"),
        bool(base.get("language_verified")),
        tuple(base.get(p) for p in parts),
    )


def resolve_workers(explicit: int | None) -> int:
    if explicit is not None:
        return max(0, explicit)
    env = os.getenv("LOAD_WORKERS")
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    return max(1, (os.cpu_count() or 1) - 1)


def _filter_language(
    rows: list[tuple[dict, dict]],
    parts: tuple,
    executor: ProcessPoolExecutor | None,
) -> list[tuple[dict, dict]]:
    """Retorna apenas as linhas cujo idioma alvo foi aceito."""
    payloads = [_payload(base, parts) for base, _ in rows]
    if executor is not None:
        slices = [payloads[i:i + SLICE] for i in range(0, len(payloads), SLICE)]
        keep = [ok for part in executor.map(decide_batch, slices) for ok in part]
    else:
        keep = [decide_target(*p) for p in payloads]

    kept: list[tuple[dict, dict]] = []
    for (base, ext), ok in zip(rows, keep):
        if ok:
            base["language"] = TARGET_LANGUAGE
            kept.append((base, ext))
    return kept


def _load_posts(
    conn: Connection,
    platform: str,
    executor: ProcessPoolExecutor | None = None,
) -> LoadResult:
    result = LoadResult(platform=platform, collection="posts")
    t0 = time.perf_counter()
    coll = get_posts_collection()

    pending: list[tuple[dict, dict]] = []

    def flush() -> None:
        if not pending:
            return
        kept = _filter_language(pending, _PARTS_POST, executor)
        result.skipped_language += len(pending) - len(kept)
        for i in range(0, len(kept), BATCH):
            counts = upsert_posts(conn, kept[i:i + BATCH], platform)
            result.inserted += counts["inserted"]
            result.modified += counts["modified"]
        pending.clear()

    for doc in coll.find({"platform": platform}, batch_size=BATCH):
        try:
            base, ext = normalize_post(doc)
        except Exception as exc:
            result.errors += 1
            result.error_samples.append(str(exc)[:120])
            continue

        pending.append((base, ext))
        if len(pending) >= CHUNK:
            flush()

    flush()

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


def _load_comments(
    conn: Connection,
    platform: str,
    executor: ProcessPoolExecutor | None = None,
) -> LoadResult:
    result = LoadResult(platform=platform, collection="comments")
    t0 = time.perf_counter()
    coll = get_comments_collection()

    pending: list[tuple[dict, dict]] = []

    def flush() -> None:
        if not pending:
            return
        kept = _filter_language(pending, _PARTS_COMMENT, executor)
        result.skipped_language += len(pending) - len(kept)
        for i in range(0, len(kept), BATCH):
            counts = upsert_comments(conn, kept[i:i + BATCH], platform)
            result.inserted += counts["inserted"]
            result.modified += counts["modified"]
        pending.clear()

    for doc in coll.find({"platform": platform}, batch_size=BATCH):
        try:
            base, ext = normalize_comment(doc)
        except Exception as exc:
            result.errors += 1
            result.error_samples.append(str(exc)[:120])
            continue

        pending.append((base, ext))
        if len(pending) >= CHUNK:
            flush()

    flush()

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


@dataclass
class AnchorResult:
    platform: str
    requested: int = 0
    inserted: int = 0
    missing_in_mongo: int = 0
    errors: int = 0


def _orphan_parents(
    conn: Connection,
    platforms: list[str] | None,
) -> dict[str, list[str]]:
    """(platform → post_external_id distintos) referenciados por comentários sem FK."""
    sql = """
        SELECT DISTINCT platform, post_external_id
        FROM comments
        WHERE post_pk IS NULL
          AND coalesce(post_external_id, '') <> ''
    """
    params: tuple = ()
    if platforms:
        sql += " AND platform = ANY(%s)"
        params = (platforms,)

    by_platform: dict[str, list[str]] = {}
    with conn.cursor() as cur:
        cur.execute(sql, params)
        for platform, pid in cur.fetchall():
            by_platform.setdefault(platform, []).append(str(pid))
    return by_platform


def _anchor_row(doc: dict) -> tuple[dict, dict]:
    base, ext = normalize_post(doc)
    base["is_anchor"] = True
    description = ext.get("description") if isinstance(ext, dict) else None
    base["language"] = detect_language_robust(
        base.get("title"), base.get("text"), description
    )
    return base, ext


def recover_orphan_parents(
    conn: Connection,
    platforms: list[str] | None = None,
) -> list[AnchorResult]:
    """Cria posts-âncora para comentários cujo post pai não entrou no corpus.

    O post pai existe no MongoDB (foi coletado), mas foi descartado na fronteira
    pt-BR. Aqui ele é reinserido com ``is_anchor = TRUE`` e o idioma real
    detectado, para que a FK ``comments.post_pk`` possa ser resolvida.
    Idempotente: reexecutar não duplica (upsert por platform+external_id).
    """
    coll = get_posts_collection()
    orphans = _orphan_parents(conn, platforms)
    results: list[AnchorResult] = []

    for platform, ids in orphans.items():
        res = AnchorResult(platform=platform, requested=len(ids))

        found: dict[str, dict] = {}
        for i in range(0, len(ids), _MONGO_LOOKUP_CHUNK):
            chunk = ids[i:i + _MONGO_LOOKUP_CHUNK]
            for doc in coll.find({"platform": platform, "external_id": {"$in": chunk}}):
                found[str(doc.get("external_id"))] = doc

        res.missing_in_mongo = len(ids) - len(found)

        pending: list[tuple[dict, dict]] = []
        for pid in ids:
            doc = found.get(pid)
            if doc is None:
                continue
            try:
                pending.append(_anchor_row(doc))
            except Exception as exc:  # noqa: BLE001 - um doc ruim não aborta a etapa
                res.errors += 1
                logger.error("anchor_normalize_error", platform=platform,
                             external_id=pid, error=str(exc))

        for i in range(0, len(pending), BATCH):
            counts = upsert_posts(conn, pending[i:i + BATCH], platform)
            res.inserted += counts["inserted"]

        logger.info(
            "anchors_recovered",
            platform=platform,
            requested=res.requested,
            inserted=res.inserted,
            missing_in_mongo=res.missing_in_mongo,
            errors=res.errors,
        )
        results.append(res)

    return results


def finalize_comments(
    conn: Connection,
    platforms: list[str] | None = None,
) -> tuple[list[AnchorResult], int]:
    """Recupera posts-âncora e resolve ``comments.post_pk``. Idempotente."""
    anchors = recover_orphan_parents(conn, platforms)
    resolved = resolve_post_fks(conn)
    logger.info("post_fks_resolved", count=resolved)
    return anchors, resolved


def run_load(
    conn: Connection,
    platforms: list[str] | None = None,
    workers: int | None = None,
) -> list[LoadResult]:
    all_platforms = [
        "reddit", "twitter", "youtube", "facebook", "instagram", "tiktok",
        "whatsapp", "telegram",
    ]
    targets = platforms or all_platforms
    results: list[LoadResult] = []

    n_workers = resolve_workers(workers)
    executor = ProcessPoolExecutor(max_workers=n_workers) if n_workers > 1 else None
    logger.info("load_workers", workers=n_workers, parallel=executor is not None)

    try:
        for platform in targets:
            logger.info("load_platform_start", platform=platform)
            results.append(_load_posts(conn, platform, executor))
            results.append(_load_comments(conn, platform, executor))
    finally:
        if executor is not None:
            executor.shutdown()

    return results
