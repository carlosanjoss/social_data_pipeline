"""
Flow de ingestão: scrapers → MongoDB Raw Lake.

Todas as plataformas rodam em paralelo (submit).
"""
from __future__ import annotations

from typing import List, Optional

from prefect import flow, get_run_logger

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]


@flow(
    name="ingest-flow",
    description="Ingere posts e comentários de todas as plataformas no MongoDB.",
    log_prints=True,
)
def ingest_flow(platforms=None):
    from flows.tasks import ingest_platform

    logger = get_run_logger()
    targets = platforms or PLATFORMS
    logger.info("Iniciando ingestao para: %s", targets)

    futures = [ingest_platform.submit(p) for p in targets]
    results = [f.result() for f in futures]

    total_posts    = sum(r["posts"]["modified"] + r["posts"]["inserted"] for r in results)
    total_comments = sum(r["comments"]["modified"] + r["comments"]["inserted"] for r in results)
    logger.info("Ingestao concluida  posts=%d  comments=%d", total_posts, total_comments)
    return results


if __name__ == "__main__":
    ingest_flow()
