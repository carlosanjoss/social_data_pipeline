"""
Flow de pipeline completo:
  1. ingest_flow   — scrapers → MongoDB
  2. validate_flow — MongoDB quality scores
  3. load_flow     — MongoDB → PostgreSQL

Cada etapa aguarda a anterior concluir (sequencial entre flows,
mas cada flow executa suas tasks de plataforma em paralelo).
"""
from __future__ import annotations

from typing import List, Optional

from prefect import flow, get_run_logger

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]


@flow(
    name="full-pipeline",
    description=(
        "Pipeline completo: ingestão dos scrapers → validação de qualidade "
        "→ carga no PostgreSQL. Agendado diariamente."
    ),
    log_prints=True,
)
def pipeline_flow(platforms=None) -> dict:
    from flows.ingest_flow import ingest_flow
    from flows.validate_flow import validate_flow
    from flows.load_flow import load_flow

    logger = get_run_logger()
    targets = platforms or PLATFORMS
    logger.info("=== Pipeline iniciado para: %s ===", targets)

    ingest_results   = ingest_flow(targets, return_state=False)
    validate_results = validate_flow(targets, return_state=False)
    load_results     = load_flow(targets, return_state=False)

    logger.info("=== Pipeline concluido ===")
    return {
        "platforms":       targets,
        "ingest":          ingest_results,
        "validate":        validate_results,
        "load":            load_results,
    }


if __name__ == "__main__":
    pipeline_flow()
