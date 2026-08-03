"""
ETL: MongoDB Raw Lake → PostgreSQL

Steps:
  1. Ensure tables exist (CREATE TABLE IF NOT EXISTS)
  2. Load posts + comments for each platform
  3. Resolve comment → post FK (post_pk)
  4. Print summary report

Run:
    python -m pipelines.load_postgres
    python -m pipelines.load_postgres --platforms reddit twitter
"""
from __future__ import annotations

import argparse
import sys
import time

from config import setup_logging, get_logger
from database.mongo import close_client as close_mongo
from database.postgres import get_conn, close_conn, create_tables
from etl.load_postgres import run_load, LoadResult
from repositories.comments import resolve_post_fks

logger = get_logger(__name__)


def print_report(results: list[LoadResult], fk_resolved: int, total_s: float) -> None:
    print("\n" + "=" * 65)
    print("LOAD POSTGRES -- RELATORIO")
    print("=" * 65)

    platform_seen: set[str] = set()
    for r in results:
        if r.platform not in platform_seen:
            platform_seen.add(r.platform)
            print(f"\n[{r.platform.upper()}]")

        status = "OK" if r.errors == 0 else f"ERROS:{r.errors}"
        print(
            f"  {r.collection:10s}  inseridos={r.inserted:6d}  "
            f"atualizados={r.modified:6d}  "
            f"fora_idioma={r.skipped_language:6d}  "
            f"{status}  {r.elapsed_s:.1f}s"
        )
        if r.error_samples:
            for sample in r.error_samples[:3]:
                print(f"    -> {sample}")

    total_ins = sum(r.inserted for r in results)
    total_mod = sum(r.modified for r in results)
    print(f"\n  FKs resolvidas (comments.post_pk): {fk_resolved}")
    print(f"\n  TOTAL  inseridos={total_ins}  atualizados={total_mod}  tempo={total_s:.1f}s")
    print("=" * 65)


def main(platforms: list[str] | None = None) -> int:
    setup_logging()
    t0 = time.perf_counter()

    conn = get_conn()
    create_tables()
    logger.info("postgres_schema_ready")

    results = run_load(conn, platforms)

    fk_resolved = resolve_post_fks(conn)
    logger.info("post_fks_resolved", count=fk_resolved)

    elapsed = time.perf_counter() - t0
    print_report(results, fk_resolved, elapsed)

    close_mongo()
    close_conn()

    has_errors = any(r.errors > 0 for r in results)
    return 1 if has_errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carrega MongoDB → PostgreSQL")
    parser.add_argument(
        "--platforms", nargs="+",
        choices=[
            "reddit", "twitter", "youtube", "facebook", "tiktok",
            "whatsapp", "telegram",
        ],
        help="Plataformas a carregar (padrao: todas)",
    )
    args = parser.parse_args()
    sys.exit(main(args.platforms))
