"""Tasks de ingestão: scrapers → MongoDB Raw Lake."""
from __future__ import annotations

from celery import shared_task

from config import setup_logging, get_logger
from pipelines.ingest_historical import ingest_platform, CONNECTORS

logger = get_logger(__name__)

PLATFORMS = list(CONNECTORS.keys())


@shared_task(
    name="tasks.ingest.ingest_platform_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def ingest_platform_task(self, platform: str) -> dict:
    """Ingere posts e comentários de uma plataforma no MongoDB."""
    setup_logging()
    logger.info("ingest_task_start", platform=platform, attempt=self.request.retries)

    result = ingest_platform(platform)

    if result.error:
        raise RuntimeError(f"ingest failed for {platform}: {result.error}")

    summary = {
        "platform":  platform,
        "posts":     result.posts,
        "comments":  result.comments,
    }
    logger.info("ingest_task_done", **summary)
    return summary


@shared_task(name="tasks.ingest.ingest_all_task", bind=True)
def ingest_all_task(self, platforms: list[str] | None = None) -> list[dict]:
    """Dispara ingestão em paralelo para todas as plataformas."""
    from celery import group
    targets = platforms or PLATFORMS
    job = group(ingest_platform_task.s(p) for p in targets)
    result = job.apply_async()
    return result.get(timeout=3600, propagate=True)
