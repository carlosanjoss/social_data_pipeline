from __future__ import annotations

from psycopg import Connection

from config import get_logger

logger = get_logger(__name__)

_UPSERT_POST = """
INSERT INTO posts (
    platform, external_id, content_type,
    title, text, url, author, author_id, language,
    published_at, like_count, share_count, comment_count,
    retweet_count, reply_count, quote_count, view_count,
    quality_score, quality_flags, is_usable,
    source_system, mongo_id, collected_at
) VALUES (
    %(platform)s, %(external_id)s, %(content_type)s,
    %(title)s, %(text)s, %(url)s, %(author)s, %(author_id)s, %(language)s,
    %(published_at)s, %(like_count)s, %(share_count)s, %(comment_count)s,
    %(retweet_count)s, %(reply_count)s, %(quote_count)s, %(view_count)s,
    %(quality_score)s, %(quality_flags)s, %(is_usable)s,
    %(source_system)s, %(mongo_id)s, %(collected_at)s
)
ON CONFLICT (platform, external_id) DO UPDATE SET
    content_type  = EXCLUDED.content_type,
    title         = EXCLUDED.title,
    text          = EXCLUDED.text,
    url           = EXCLUDED.url,
    author        = EXCLUDED.author,
    author_id     = EXCLUDED.author_id,
    language      = EXCLUDED.language,
    published_at  = EXCLUDED.published_at,
    like_count    = EXCLUDED.like_count,
    share_count   = EXCLUDED.share_count,
    comment_count = EXCLUDED.comment_count,
    retweet_count = EXCLUDED.retweet_count,
    reply_count   = EXCLUDED.reply_count,
    quote_count   = EXCLUDED.quote_count,
    view_count    = EXCLUDED.view_count,
    quality_score = EXCLUDED.quality_score,
    quality_flags = EXCLUDED.quality_flags,
    is_usable     = EXCLUDED.is_usable,
    source_system = EXCLUDED.source_system,
    mongo_id      = EXCLUDED.mongo_id,
    collected_at  = EXCLUDED.collected_at
RETURNING id, (xmax = 0) AS inserted
"""

_EXT_SQL: dict[str, str] = {
    "reddit": """
        INSERT INTO reddit_posts (post_id, score, num_comments, subreddit)
        VALUES (%(post_id)s, %(score)s, %(num_comments)s, %(subreddit)s)
        ON CONFLICT (post_id) DO UPDATE SET
            score        = EXCLUDED.score,
            num_comments = EXCLUDED.num_comments,
            subreddit    = EXCLUDED.subreddit
    """,
    "twitter": """
        INSERT INTO twitter_tweets (post_id, conversation_id, group_name, hashtags)
        VALUES (%(post_id)s, %(conversation_id)s, %(group_name)s, %(hashtags)s)
        ON CONFLICT (post_id) DO UPDATE SET
            conversation_id = EXCLUDED.conversation_id,
            group_name      = EXCLUDED.group_name,
            hashtags        = EXCLUDED.hashtags
    """,
    "youtube": """
        INSERT INTO youtube_videos (post_id, channel_id, channel_title, description, duration, thumbnail_url, tags)
        VALUES (%(post_id)s, %(channel_id)s, %(channel_title)s, %(description)s, %(duration)s, %(thumbnail_url)s, %(tags)s)
        ON CONFLICT (post_id) DO UPDATE SET
            channel_id    = EXCLUDED.channel_id,
            channel_title = EXCLUDED.channel_title,
            description   = EXCLUDED.description,
            duration      = EXCLUDED.duration,
            thumbnail_url = EXCLUDED.thumbnail_url,
            tags          = EXCLUDED.tags
    """,
    "facebook": """
        INSERT INTO facebook_posts (post_id, page_id, page_slug, reactions, media_types)
        VALUES (%(post_id)s, %(page_id)s, %(page_slug)s, %(reactions)s, %(media_types)s)
        ON CONFLICT (post_id) DO UPDATE SET
            page_id     = EXCLUDED.page_id,
            page_slug   = EXCLUDED.page_slug,
            reactions   = EXCLUDED.reactions,
            media_types = EXCLUDED.media_types
    """,
    "tiktok": """
        INSERT INTO tiktok_videos (post_id, video_url)
        VALUES (%(post_id)s, %(video_url)s)
        ON CONFLICT (post_id) DO UPDATE SET
            video_url = EXCLUDED.video_url
    """,
    "whatsapp": """
        INSERT INTO whatsapp_messages
            (post_id, group_id, member_id, score_sentiment, score_misinformation,
             matched_terms, collection_periods)
        VALUES
            (%(post_id)s, %(group_id)s, %(member_id)s, %(score_sentiment)s,
             %(score_misinformation)s, %(matched_terms)s, %(collection_periods)s)
        ON CONFLICT (post_id) DO UPDATE SET
            group_id             = EXCLUDED.group_id,
            member_id            = EXCLUDED.member_id,
            score_sentiment      = EXCLUDED.score_sentiment,
            score_misinformation = EXCLUDED.score_misinformation,
            matched_terms        = EXCLUDED.matched_terms,
            collection_periods   = EXCLUDED.collection_periods
    """,
    "telegram": """
        INSERT INTO telegram_messages
            (post_id, group_id, member_id, score_sentiment, score_misinformation,
             matched_terms, collection_periods)
        VALUES
            (%(post_id)s, %(group_id)s, %(member_id)s, %(score_sentiment)s,
             %(score_misinformation)s, %(matched_terms)s, %(collection_periods)s)
        ON CONFLICT (post_id) DO UPDATE SET
            group_id             = EXCLUDED.group_id,
            member_id            = EXCLUDED.member_id,
            score_sentiment      = EXCLUDED.score_sentiment,
            score_misinformation = EXCLUDED.score_misinformation,
            matched_terms        = EXCLUDED.matched_terms,
            collection_periods   = EXCLUDED.collection_periods
    """,
}


def upsert_posts(
    conn: Connection,
    rows: list[tuple[dict, dict]],
    platform: str,
) -> dict[str, int]:
    inserted = modified = 0
    ext_sql = _EXT_SQL.get(platform)

    with conn.cursor() as cur:
        for base, ext in rows:
            cur.execute(_UPSERT_POST, base)
            row = cur.fetchone()
            post_id, was_inserted = row[0], row[1]
            if was_inserted:
                inserted += 1
            else:
                modified += 1

            if ext_sql and ext:
                cur.execute(ext_sql, {"post_id": post_id, **ext})

    conn.commit()
    return {"inserted": inserted, "modified": modified}
