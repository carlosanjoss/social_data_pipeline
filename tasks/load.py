"""Tasks de carga: MongoDB → PostgreSQL."""
from __future__ import annotations

from celery import shared_task

from config import setup_logging, get_logger
from database.postgres import get_conn, close_conn, create_tables
from etl.load_postgres import run_load, LoadResult

logger = get_logger(__name__)


@shared_task(
    name="tasks.load.load_platform_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def load_platform_task(self, platform: str) -> dict:
    """Carrega posts + comments de uma plataforma do MongoDB → PostgreSQL."""
    setup_logging()
    logger.info("load_task_start", platform=platform, attempt=self.request.retries)

    conn = get_conn()
    create_tables()

    results: list[LoadResult] = run_load(conn, [platform])
    close_conn()

    summary = {}
    for r in results:
        summary[r.collection] = {
            "inserted": r.inserted,
            "modified": r.modified,
            "errors":   r.errors,
        }
        if r.errors:
            raise RuntimeError(
                f"load errors for {platform}/{r.collection}: {r.error_samples[:3]}"
            )

    logger.info("load_task_done", platform=platform, summary=summary)
    return {"platform": platform, **summary}


@shared_task(name="tasks.load.load_all_task", bind=True)
def load_all_task(self, platforms: list[str] | None = None) -> list[dict]:
    from celery import group
    from repositories.comments import resolve_post_fks

    targets = platforms or ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]
    job = group(load_platform_task.s(p) for p in targets)
    results = job.apply_async().get(timeout=7200, propagate=True)

    # Resolve FK cross-platform after all platforms are loaded
    conn = get_conn()
    resolved = resolve_post_fks(conn)
    close_conn()
    logger.info("post_fks_resolved", count=resolved)

    return results
