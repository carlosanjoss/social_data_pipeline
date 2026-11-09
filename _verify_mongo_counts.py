import json
import sqlite3
import tempfile
from pathlib import Path

from connectors import CONNECTORS
from database.mongo import get_comments_collection, get_posts_collection

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "instagram", "tiktok"]
BATCH = 5000


def chunks(cursor, size):
    batch = []
    for row in cursor:
        batch.append(row[0])
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


with tempfile.TemporaryDirectory() as temp_dir:
    db_path = Path(temp_dir) / "source_ids.sqlite3"
    sql = sqlite3.connect(db_path)
    sql.execute(
        "CREATE TABLE source_ids (platform TEXT, kind TEXT, external_id TEXT, "
        "PRIMARY KEY (platform, kind, external_id))"
    )

    for platform in PLATFORMS:
        connector = CONNECTORS[platform]()
        for kind, iterator in (
            ("posts", connector.iter_posts()),
            ("comments", connector.iter_comments()),
        ):
            pending = []
            for doc in iterator:
                external_id = str(doc.get("external_id") or "")
                if not external_id:
                    continue
                pending.append((platform, kind, external_id))
                if len(pending) >= BATCH:
                    sql.executemany("INSERT OR IGNORE INTO source_ids VALUES (?,?,?)", pending)
                    sql.commit()
                    pending.clear()
            if pending:
                sql.executemany("INSERT OR IGNORE INTO source_ids VALUES (?,?,?)", pending)
                sql.commit()
            total = sql.execute(
                "SELECT COUNT(*) FROM source_ids WHERE platform=? AND kind=?",
                (platform, kind),
            ).fetchone()[0]
            print(f"INDEXED {platform} {kind} {total}", flush=True)

    mongo_collections = {
        "posts": get_posts_collection(),
        "comments": get_comments_collection(),
    }
    report = {}
    for platform in PLATFORMS:
        report[platform] = {}
        for kind, collection in mongo_collections.items():
            source_total = sql.execute(
                "SELECT COUNT(*) FROM source_ids WHERE platform=? AND kind=?",
                (platform, kind),
            ).fetchone()[0]
            mongo_total = collection.count_documents({"platform": platform})
            matched = 0
            missing_samples = []
            cursor = sql.execute(
                "SELECT external_id FROM source_ids WHERE platform=? AND kind=? ORDER BY external_id",
                (platform, kind),
            )
            for ids in chunks(cursor, BATCH):
                found = set(collection.distinct(
                    "external_id",
                    {"platform": platform, "external_id": {"$in": ids}},
                ))
                matched += len(found)
                if len(missing_samples) < 10:
                    missing_samples.extend(item for item in ids if item not in found)
                    missing_samples = missing_samples[:10]
            report[platform][kind] = {
                "source_unique": source_total,
                "mongo": mongo_total,
                "source_present": matched,
                "missing": source_total - matched,
                "mongo_extra": mongo_total - matched,
                "missing_samples": missing_samples,
            }

    print("FINAL_REPORT")
    print(json.dumps(report, ensure_ascii=False, indent=2))
