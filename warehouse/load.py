"""
ETL: PostgreSQL → DuckDB Star Schema

Ordem de carga:
  1. Dimensões estáticas (platform, content_type, date)
  2. Dimensões com lookup no PG (location, author)
  3. Fatos (posts, comments)

Run:
    python -m warehouse.load
    python -m warehouse.load --report
"""
from __future__ import annotations

import argparse
import sys
import time

from config import setup_logging, get_logger
from warehouse.client import get_conn, close_conn, apply_schema
from warehouse.etl import (
    load_dim_date, load_dim_platform, load_dim_content_type,
    load_dim_location, load_dim_author,
    load_fact_posts, load_fact_comments,
)

logger = get_logger(__name__)


def run_load() -> dict[str, int]:
    t0 = time.perf_counter()
    conn = get_conn()
    apply_schema()

    steps = [
        ("dim_platform",     lambda: load_dim_platform(conn)),
        ("dim_content_type", lambda: load_dim_content_type(conn)),
        ("dim_date",         lambda: load_dim_date(conn)),
        ("dim_location",     lambda: load_dim_location(conn)),
        ("dim_author",       lambda: load_dim_author(conn)),
        ("fact_posts",       lambda: load_fact_posts(conn)),
        ("fact_comments",    lambda: load_fact_comments(conn)),
    ]

    counts: dict[str, int] = {}
    for name, fn in steps:
        t_step = time.perf_counter()
        n = fn()
        counts[name] = n
        logger.info("step_done", step=name, rows=n, elapsed_s=round(time.perf_counter() - t_step, 2))

    counts["_elapsed_s"] = round(time.perf_counter() - t0, 1)
    return counts


def print_report(counts: dict[str, int]) -> None:
    print("\n" + "=" * 55)
    print("DATA WAREHOUSE — RELATORIO")
    print("=" * 55)
    for k, v in counts.items():
        if k.startswith("_"):
            continue
        print(f"  {k:<22s}  {v:>8,d} linhas")
    print(f"\n  Tempo total: {counts.get('_elapsed_s', '?')}s")
    print("=" * 55)


def run_analytical_report(conn) -> None:
    from warehouse.queries import (
        posts_por_plataforma_dia, distribuicao_qualidade,
        top_subreddits, hierarquia_comentarios,
    )

    print("\n--- Posts por plataforma/mes ---")
    for row in posts_por_plataforma_dia(conn):
        avg_q = f"{row[5]:.1f}" if row[5] is not None else "N/A"
        print(f"  {row[0]:10s} {row[1]}-{row[2]:02d}  posts={row[3]}  likes={row[4]}  avg_q={avg_q}")

    print("\n--- Distribuição de qualidade ---")
    for row in distribuicao_qualidade(conn):
        print(f"  {row[0]:10s} {row[1]:8s}  total={row[2]:6d}  avg={row[3]:.1f}  usaveis={row[5]}%")

    print("\n--- Top 10 subreddits ---")
    for row in top_subreddits(conn, n=10):
        print(f"  r/{row[0]:30s}  posts={row[1]:5d}  avg_q={row[2]:.1f}")

    print("\n--- Hierarquia de comentários ---")
    for row in hierarquia_comentarios(conn):
        print(f"  {row[0]:10s}  reply={row[1]}  total={row[2]:7d}  avg_depth={row[3] or 0:.1f}")


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true", help="Exibe queries analíticas após a carga")
    args = parser.parse_args()

    counts = run_load()
    print_report(counts)

    if args.report:
        run_analytical_report(get_conn())

    close_conn()
    return 0


if __name__ == "__main__":
    sys.exit(main())
