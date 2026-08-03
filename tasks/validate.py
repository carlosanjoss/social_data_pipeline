"""Tasks de validação de qualidade: MongoDB → quality scores."""
from __future__ import annotations

from celery import shared_task

from config import setup_logging, get_logger
from etl.validate_mongo import run_validation, PlatformStats

logger = get_logger(__name__)


@shared_task(
    name="tasks.validate.validate_platform_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def validate_platform_task(self, platform: str) -> dict:
    """Computa quality scores para todos os docs de uma plataforma."""
    setup_logging()
    logger.info("validate_task_start", platform=platform, attempt=self.request.retries)

    stats_list: list[PlatformStats] = run_validation([platform])

    summary = {}
    for s in stats_list:
        summary[s.collection] = {
            "total":      s.total,
            "valid":      s.valid,
            "invalid":    s.invalid,
            "usable":     s.usable,
            "avg_score":  s.avg_score,
        }

    logger.info("validate_task_done", platform=platform, summary=summary)
    return {"platform": platform, **summary}


@shared_task(name="tasks.validate.validate_all_task", bind=True)
def validate_all_task(self, platforms: list[str] | None = None) -> list[dict]:
    from celery import group
    targets = platforms or ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]
    job = group(validate_platform_task.s(p) for p in targets)
    return job.apply_async().get(timeout=3600, propagate=True)
