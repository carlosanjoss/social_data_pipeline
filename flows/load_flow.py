"""
Flow de carga: MongoDB → PostgreSQL.

Plataformas rodam em paralelo; FKs são resolvidas ao final.
"""
from __future__ import annotations

from typing import List, Optional

from prefect import flow, get_run_logger

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]


@flow(
    name="load-postgres-flow",
    description="Carrega dados do MongoDB para o PostgreSQL (IS-A schema).",
    log_prints=True,
)
def load_flow(platforms=None):
    from flows.tasks import load_platform_postgres, resolve_comment_fks

    logger = get_run_logger()
    targets = platforms or PLATFORMS
    logger.info("Iniciando carga para: %s", targets)

    futures = [load_platform_postgres.submit(p) for p in targets]
    results = [f.result() for f in futures]

    fks = resolve_comment_fks()

    total_ins = sum(
        sum(c.get("inserted", 0) for c in r.values() if isinstance(c, dict))
        for r in results
    )
    total_mod = sum(
        sum(c.get("modified", 0) for c in r.values() if isinstance(c, dict))
        for r in results
    )
    logger.info(
        "Carga concluida  inseridos=%d  atualizados=%d  fks=%d",
        total_ins, total_mod, fks,
    )
    return {"results": results, "fks_resolved": fks}


if __name__ == "__main__":
    load_flow()
