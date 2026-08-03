"""
Tasks compostas: chain ingest → validate → load por plataforma,
e chord para executar todas as plataformas em paralelo.
"""
from __future__ import annotations

from celery import chain, chord, shared_task

from config import setup_logging, get_logger
from tasks.ingest import ingest_platform_task
from tasks.validate import validate_platform_task
from tasks.load import load_platform_task

logger = get_logger(__name__)

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]


def platform_chain(platform: str):
    """ingest → validate → load para uma plataforma (executados em sequência)."""
    return chain(
        ingest_platform_task.s(platform),
        validate_platform_task.si(platform),   # .si ignora resultado anterior
        load_platform_task.si(platform),
    )


@shared_task(name="tasks.pipeline.run_platform_pipeline")
def run_platform_pipeline(platform: str) -> dict:
    """Executa o pipeline completo para uma única plataforma."""
    setup_logging()
    logger.info("pipeline_start", platform=platform)
    result = platform_chain(platform).apply_async().get(timeout=7200, propagate=True)
    logger.info("pipeline_done", platform=platform)
    return {"platform": platform, "result": result}


@shared_task(name="tasks.pipeline.run_full_pipeline")
def run_full_pipeline(platforms: list[str] | None = None) -> dict:
    """
    Executa o pipeline completo para todas as plataformas em paralelo (chord).
    Cada plataforma roda de forma independente: ingest → validate → load.
    Ao final, resolve os FKs de comments → posts no PostgreSQL.
    """
    setup_logging()
    targets = platforms or PLATFORMS
    logger.info("full_pipeline_start", platforms=targets)

    job = chord(
        (platform_chain(p) for p in targets),
        _resolve_fks_callback.s(),
    )
    result = job.apply_async().get(timeout=14_400, propagate=True)
    logger.info("full_pipeline_done", platforms=targets)
    return {"platforms": targets, "fk_result": result}


@shared_task(name="tasks.pipeline._resolve_fks_callback")
def _resolve_fks_callback(results: list) -> dict:
    """Callback do chord: resolve FKs após todas as plataformas carregadas."""
    from database.postgres import get_conn, close_conn
    from repositories.comments import resolve_post_fks

    conn = get_conn()
    count = resolve_post_fks(conn)
    close_conn()
    logger.info("post_fks_resolved", count=count)
    return {"fks_resolved": count, "platform_results": results}
