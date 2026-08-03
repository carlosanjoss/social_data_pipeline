"""
Flow de validação de qualidade: MongoDB → quality scores.

Plataformas rodam em paralelo.
"""
from __future__ import annotations

from typing import List, Optional

from prefect import flow, get_run_logger

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]


@flow(
    name="validate-flow",
    description="Computa quality scores nos documentos do MongoDB.",
    log_prints=True,
)
def validate_flow(platforms=None):
    from flows.tasks import validate_platform

    logger = get_run_logger()
    targets = platforms or PLATFORMS
    logger.info("Iniciando validacao para: %s", targets)

    futures = [validate_platform.submit(p) for p in targets]
    results = [f.result() for f in futures]

    logger.info("Validacao concluida para %d plataformas", len(results))
    return results


if __name__ == "__main__":
    validate_flow()
