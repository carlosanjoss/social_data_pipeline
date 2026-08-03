from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.collection import Collection

from .client import get_db

COLLECTION_POSTS    = "raw_posts"
COLLECTION_COMMENTS = "raw_comments"
COLLECTION_RUNS     = "scraping_runs"


def get_posts_collection() -> Collection:
    return get_db()[COLLECTION_POSTS]


def get_comments_collection() -> Collection:
    return get_db()[COLLECTION_COMMENTS]


def get_runs_collection() -> Collection:
    return get_db()[COLLECTION_RUNS]


def ensure_indexes() -> None:
    posts = get_posts_collection()
    posts.create_indexes([
        IndexModel([("platform", ASCENDING), ("external_id", ASCENDING)], unique=True, name="platform_external_id"),
        IndexModel([("platform", ASCENDING)], name="platform"),
        IndexModel([("collected_at", DESCENDING)], name="collected_at"),
        IndexModel([("normalized.published_at", DESCENDING)], name="published_at"),
        IndexModel([("normalized.subreddit", ASCENDING)], name="subreddit", sparse=True),
        IndexModel([("normalized.channel_id", ASCENDING)], name="channel_id", sparse=True),
        IndexModel([("normalized.page_id", ASCENDING)], name="page_id", sparse=True),
        IndexModel([("normalized.group_id", ASCENDING)], name="group_id", sparse=True),
    ])

    comments = get_comments_collection()
    comments.create_indexes([
        IndexModel([("platform", ASCENDING), ("external_id", ASCENDING)], unique=True, name="platform_external_id"),
        IndexModel([("platform", ASCENDING)], name="platform"),
        IndexModel([("normalized.post_id", ASCENDING)], name="post_id"),
        IndexModel([("collected_at", DESCENDING)], name="collected_at"),
    ])

    runs = get_runs_collection()
    runs.create_indexes([
        IndexModel([("platform", ASCENDING), ("started_at", DESCENDING)], name="platform_started"),
    ])
