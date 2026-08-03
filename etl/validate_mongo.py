"""
Reads every document from raw_posts and raw_comments, validates it with
Pydantic, computes a quality score, and writes normalized.quality back
to MongoDB in bulk.

Run:
    python -m etl.validate_mongo
    python -m etl.validate_mongo --platforms reddit twitter
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field

from pymongo import UpdateOne
from pymongo.collection import Collection

from config import settings, setup_logging, get_logger
from database.mongo import get_posts_collection, get_comments_collection, close_client
from validators import validate_post, validate_comment

logger = get_logger(__name__)

BATCH = settings.batch_size


@dataclass
class PlatformStats:
    platform: str
    collection: str
    total: int = 0
    valid: int = 0
    invalid: int = 0
    usable: int = 0
    elapsed_s: float = 0.0
    score_sum: float = 0.0
    flag_counts: dict[str, int] = field(default_factory=dict)

    @property
    def avg_score(self) -> float:
        return round(self.score_sum / self.total, 1) if self.total else 0.0


def _run_collection(
    collection: Collection,
    platform: str,
    validator_fn,
    collection_label: str,
) -> PlatformStats:
    stats = PlatformStats(platform=platform, collection=collection_label)
    t0 = time.perf_counter()

    cursor = collection.find({"platform": platform}, batch_size=BATCH)
    ops: list[UpdateOne] = []

    for doc in cursor:
        stats.total += 1
        model, errors = validator_fn(doc)

        if errors:
            stats.invalid += 1
            logger.warning(
                "validation_errors",
                platform=platform,
                external_id=doc.get("external_id"),
                errors=errors[:3],
            )
            quality_dict = {"score": 0.0, "flags": ["pydantic_error"], "is_usable": False}
        else:
            stats.valid += 1
            quality_dict = model.quality.model_dump()

        if quality_dict["is_usable"]:
            stats.usable += 1
        stats.score_sum += quality_dict["score"]
        for flag in quality_dict["flags"]:
            stats.flag_counts[flag] = stats.flag_counts.get(flag, 0) + 1

        ops.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"normalized.quality": quality_dict}},
        ))

        if len(ops) >= BATCH:
            collection.bulk_write(ops, ordered=False)
            ops.clear()

    if ops:
        collection.bulk_write(ops, ordered=False)

    stats.elapsed_s = time.perf_counter() - t0
    return stats


def run_validation(platforms: list[str] | None = None) -> list[PlatformStats]:
    all_platforms = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]
    platforms = platforms or all_platforms

    posts_coll    = get_posts_collection()
    comments_coll = get_comments_collection()
    all_stats: list[PlatformStats] = []

    for platform in platforms:
        logger.info("validating_platform", platform=platform)
        s1 = _run_collection(posts_coll,    platform, validate_post,    "raw_posts")
        s2 = _run_collection(comments_coll, platform, validate_comment, "raw_comments")
        all_stats.extend([s1, s2])

    return all_stats


def print_report(stats: list[PlatformStats]) -> None:
    print("\n" + "=" * 65)
    print("DATA QUALITY REPORT")
    print("=" * 65)

    platforms_seen: set[str] = set()
    for s in stats:
        if s.platform not in platforms_seen:
            platforms_seen.add(s.platform)
            print(f"\n[{s.platform.upper()}]")

        if s.total == 0:
            print(f"  {s.collection}: sem documentos")
            continue

        usable_pct = round(100 * s.usable / s.total, 1)
        print(f"  {s.collection}:")
        print(f"    total={s.total}  validos={s.valid}  invalidos={s.invalid}")
        print(f"    score_medio={s.avg_score}/100  utilizaveis={s.usable} ({usable_pct}%)")
        if s.flag_counts:
            top_flags = sorted(s.flag_counts.items(), key=lambda x: -x[1])[:5]
            print(f"    flags_top5: {top_flags}")
        print(f"    tempo: {s.elapsed_s:.1f}s")

    print("\n" + "=" * 65)


def main(platforms: list[str] | None = None) -> int:
    setup_logging()
    stats = run_validation(platforms)
    print_report(stats)
    close_client()
    has_errors = any(s.invalid > 0 for s in stats)
    return 1 if has_errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validacao de qualidade no MongoDB")
    parser.add_argument(
        "--platforms", nargs="+",
        choices=["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"],
        help="Plataformas a validar (padrao: todas)",
    )
    args = parser.parse_args()
    sys.exit(main(args.platforms))
