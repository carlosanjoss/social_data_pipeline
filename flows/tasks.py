"""
Prefect @task wrappers em torno das funções ETL existentes.
Cada task tem retry automático com backoff progressivo.
"""
from __future__ import annotations

from prefect import task, get_run_logger


@task(
    name="ingest-platform",
    retries=3,
    retry_delay_seconds=[30, 90, 300],   # 30 s → 90 s → 5 min
    tags=["ingest"],
    timeout_seconds=1800,
)
def ingest_platform(platform: str) -> dict:
    from pipelines.ingest_historical import ingest_platform as _ingest
    logger = get_run_logger()
    logger.info("ingest start: %s", platform)
    result = _ingest(platform)
    if result.error:
        raise RuntimeError(f"ingest failed for {platform}: {result.error}")
    summary = {
        "platform": platform,
        "posts":    result.posts,
        "comments": result.comments,
    }
    logger.info("ingest done: %s  posts=%s comments=%s", platform, result.posts, result.comments)
    return summary


@task(
    name="validate-platform",
    retries=2,
    retry_delay_seconds=[30, 120],
    tags=["validate"],
    timeout_seconds=600,
)
def validate_platform(platform: str) -> dict:
    from etl.validate_mongo import run_validation
    logger = get_run_logger()
    logger.info("validate start: %s", platform)
    stats_list = run_validation([platform])
    summary = {
        s.collection: {
            "total":     s.total,
            "valid":     s.valid,
            "usable":    s.usable,
            "avg_score": s.avg_score,
        }
        for s in stats_list
    }
    logger.info("validate done: %s", platform)
    return {"platform": platform, **summary}


@task(
    name="load-platform-postgres",
    retries=3,
    retry_delay_seconds=[30, 90, 300],
    tags=["load"],
    timeout_seconds=3600,
)
def load_platform_postgres(platform: str) -> dict:
    from database.postgres import get_conn, close_conn, create_tables
    from etl.load_postgres import run_load
    logger = get_run_logger()
    logger.info("load start: %s", platform)

    conn = get_conn()
    create_tables()
    results = run_load(conn, [platform])
    close_conn()

    for r in results:
        if r.errors:
            raise RuntimeError(
                f"load errors {platform}/{r.collection}: {r.error_samples[:2]}"
            )

    summary = {
        r.collection: {"inserted": r.inserted, "modified": r.modified}
        for r in results
    }
    logger.info("load done: %s", platform)
    return {"platform": platform, **summary}


@task(
    name="resolve-comment-fks",
    retries=2,
    retry_delay_seconds=[30, 60],
    tags=["load"],
)
def resolve_comment_fks() -> int:
    from database.postgres import get_conn, close_conn
    from repositories.comments import resolve_post_fks
    logger = get_run_logger()
    conn = get_conn()
    count = resolve_post_fks(conn)
    close_conn()
    logger.info("FKs resolved: %d", count)
    return count
