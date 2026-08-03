"""
Ingests all historical JSON data from the 4 scrapers into MongoDB.

Usage (from social_data_pipeline/):
    python -m pipelines.ingest_historical
    python -m pipelines.ingest_historical --platforms reddit twitter
"""
import argparse
import sys
import time
from dataclasses import dataclass, field

from config import setup_logging, get_logger
from connectors import CONNECTORS
from database.mongo import ensure_indexes, close_client
from etl.extract import extract_posts, extract_comments
from etl.load_mongo import load_posts, load_comments

logger = get_logger(__name__)


@dataclass
class PlatformResult:
    platform:  str
    posts:     dict[str, int] = field(default_factory=dict)
    comments:  dict[str, int] = field(default_factory=dict)
    elapsed_s: float = 0.0
    error:     str | None = None


def ingest_platform(platform: str) -> PlatformResult:
    result = PlatformResult(platform=platform)
    t0 = time.perf_counter()

    try:
        connector_cls = CONNECTORS[platform]
        connector = connector_cls()

        logger.info("ingest_start", platform=platform)

        result.posts    = load_posts(extract_posts(connector))
        result.comments = load_comments(extract_comments(connector))

    except Exception as exc:
        result.error = str(exc)
        logger.error("ingest_platform_error", platform=platform, error=str(exc), exc_info=True)

    result.elapsed_s = time.perf_counter() - t0
    return result


def print_report(results: list[PlatformResult]) -> None:
    print("\n" + "=" * 60)
    print("INGESTAO HISTORICA -- RELATORIO")
    print("=" * 60)

    grand_inserted = grand_errors = 0

    for r in results:
        print(f"\n[{r.platform.upper()}]")
        if r.error:
            print(f"   ERRO: {r.error}")
            continue

        def _fmt(d: dict) -> str:
            return (
                f"inseridos={d.get('inserted',0)}  "
                f"atualizados={d.get('modified',0)}  "
                f"ignorados={d.get('skipped',0)}  "
                f"erros={d.get('errors',0)}"
            )

        print(f"   posts:      {_fmt(r.posts)}")
        print(f"   comentários:{_fmt(r.comments)}")
        print(f"   tempo: {r.elapsed_s:.1f}s")

        grand_inserted += r.posts.get("inserted", 0) + r.comments.get("inserted", 0)
        grand_errors   += r.posts.get("errors",   0) + r.comments.get("errors",   0)

    print("\n" + "-" * 60)
    print(f"Total inseridos: {grand_inserted}  |  Total erros: {grand_errors}")
    print("=" * 60 + "\n")


def main(platforms: list[str] | None = None) -> int:
    setup_logging()
    platforms = platforms or list(CONNECTORS.keys())

    logger.info("ensuring_mongo_indexes")
    ensure_indexes()

    results = [ingest_platform(p) for p in platforms]
    print_report(results)
    close_client()

    has_errors = any(r.error for r in results)
    return 1 if has_errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão histórica para MongoDB")
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=list(CONNECTORS.keys()),
        help="Plataformas a ingerir (padrão: todas)",
    )
    args = parser.parse_args()
    sys.exit(main(args.platforms))
