from __future__ import annotations

from psycopg import Connection

from config import get_logger

logger = get_logger(__name__)

_UPSERT_COMMENT = """
INSERT INTO comments (
    platform, external_id, content_type,
    text, author, author_id, language,
    post_external_id, parent_external_id,
    is_reply, depth, published_at,
    like_count, reply_count,
    quality_score, quality_flags, is_usable,
    source_system, mongo_id, collected_at
) VALUES (
    %(platform)s, %(external_id)s, %(content_type)s,
    %(text)s, %(author)s, %(author_id)s, %(language)s,
    %(post_external_id)s, %(parent_external_id)s,
    %(is_reply)s, %(depth)s, %(published_at)s,
    %(like_count)s, %(reply_count)s,
    %(quality_score)s, %(quality_flags)s, %(is_usable)s,
    %(source_system)s, %(mongo_id)s, %(collected_at)s
)
ON CONFLICT (platform, external_id) DO UPDATE SET
    content_type       = EXCLUDED.content_type,
    text               = EXCLUDED.text,
    author             = EXCLUDED.author,
    author_id          = EXCLUDED.author_id,
    language           = EXCLUDED.language,
    post_external_id   = EXCLUDED.post_external_id,
    parent_external_id = EXCLUDED.parent_external_id,
    is_reply           = EXCLUDED.is_reply,
    depth              = EXCLUDED.depth,
    published_at       = EXCLUDED.published_at,
    like_count         = EXCLUDED.like_count,
    reply_count        = EXCLUDED.reply_count,
    quality_score      = EXCLUDED.quality_score,
    quality_flags      = EXCLUDED.quality_flags,
    is_usable          = EXCLUDED.is_usable,
    source_system      = EXCLUDED.source_system,
    mongo_id           = EXCLUDED.mongo_id,
    collected_at       = EXCLUDED.collected_at
RETURNING id, (xmax = 0) AS inserted
"""

_EXT_SQL: dict[str, str] = {
    "reddit": """
        INSERT INTO reddit_comments (comment_id, score, subreddit, is_reply_to_comment)
        VALUES (%(comment_id)s, %(score)s, %(subreddit)s, %(is_reply_to_comment)s)
        ON CONFLICT (comment_id) DO UPDATE SET
            score               = EXCLUDED.score,
            subreddit           = EXCLUDED.subreddit,
            is_reply_to_comment = EXCLUDED.is_reply_to_comment
    """,
    "youtube": """
        INSERT INTO youtube_comments (comment_id, video_id)
        VALUES (%(comment_id)s, %(video_id)s)
        ON CONFLICT (comment_id) DO UPDATE SET
            video_id = EXCLUDED.video_id
    """,
    "facebook": """
        INSERT INTO facebook_comments (comment_id, page_slug)
        VALUES (%(comment_id)s, %(page_slug)s)
        ON CONFLICT (comment_id) DO UPDATE SET
            page_slug = EXCLUDED.page_slug
    """,
    "tiktok": """
        INSERT INTO tiktok_comments (comment_id, video_id)
        VALUES (%(comment_id)s, %(video_id)s)
        ON CONFLICT (comment_id) DO UPDATE SET
            video_id = EXCLUDED.video_id
    """,
}


def upsert_comments(
    conn: Connection,
    rows: list[tuple[dict, dict]],
    platform: str,
) -> dict[str, int]:
    inserted = modified = 0
    ext_sql = _EXT_SQL.get(platform)

    with conn.cursor() as cur:
        for base, ext in rows:
            cur.execute(_UPSERT_COMMENT, base)
            row = cur.fetchone()
            comment_id, was_inserted = row[0], row[1]
            if was_inserted:
                inserted += 1
            else:
                modified += 1

            if ext_sql and ext:
                cur.execute(ext_sql, {"comment_id": comment_id, **ext})

    conn.commit()
    return {"inserted": inserted, "modified": modified}


def resolve_post_fks(conn: Connection) -> int:
    """Back-fill comments.post_pk by joining on (platform, post_external_id)."""
    sql = """
        UPDATE comments c
        SET    post_pk = p.id
        FROM   posts p
        WHERE  c.platform         = p.platform
          AND  c.post_external_id = p.external_id
          AND  c.post_pk IS NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        count = cur.rowcount
    conn.commit()
    return count
