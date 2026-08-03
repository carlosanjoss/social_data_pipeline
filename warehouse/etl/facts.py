"""
Carga das tabelas fato a partir do PostgreSQL (via DuckDB postgres extension).
"""
from __future__ import annotations

from duckdb import DuckDBPyConnection

from config import get_logger

logger = get_logger(__name__)


def load_fact_posts(conn: DuckDBPyConnection) -> int:
    conn.execute("""
        INSERT OR IGNORE INTO fact_posts
        SELECT
            p.id                                                 AS post_key,
            CAST(strftime(p.published_at::DATE, '%Y%m%d') AS INTEGER) AS date_key,
            dp.platform_key,
            dct.content_type_key,
            da.author_key,
            dl.location_key,
            p.external_id,
            p.id                                                 AS postgres_id,
            p.like_count,
            p.share_count,
            p.comment_count,
            p.retweet_count,
            p.reply_count,
            p.quote_count,
            p.view_count,
            p.quality_score,
            p.is_usable,
            (p.text IS NOT NULL AND length(p.text) > 0)         AS has_text,
            CASE WHEN p.text IS NOT NULL THEN length(p.text) ELSE 0 END AS text_length
        FROM pg.public.posts p
        JOIN  dim_platform     dp  ON dp.platform     = p.platform
        JOIN  dim_content_type dct ON dct.content_type = p.content_type
        LEFT JOIN (
            SELECT platform, author, author_key,
                   ROW_NUMBER() OVER (PARTITION BY platform, author ORDER BY effective_from DESC) AS rn
            FROM dim_author WHERE is_current = TRUE
        ) da ON da.platform = p.platform
            AND da.author   = COALESCE(p.author, '<unknown>')
            AND da.rn = 1
        LEFT JOIN (
            SELECT
                'reddit'  AS platform, subreddit AS location, post_id FROM pg.public.reddit_posts
            UNION ALL
            SELECT 'youtube', channel_id, post_id FROM pg.public.youtube_videos
            UNION ALL
            SELECT 'facebook', page_slug, post_id FROM pg.public.facebook_posts
            UNION ALL
            SELECT 'twitter', group_name, post_id FROM pg.public.twitter_tweets WHERE group_name IS NOT NULL
            UNION ALL
            SELECT 'whatsapp', group_id, post_id FROM pg.public.whatsapp_messages WHERE group_id IS NOT NULL
            UNION ALL
            SELECT 'telegram', group_id, post_id FROM pg.public.telegram_messages WHERE group_id IS NOT NULL
        ) ploc ON ploc.post_id = p.id
        LEFT JOIN dim_location dl ON dl.platform = ploc.platform AND dl.location = ploc.location
        WHERE p.published_at IS NOT NULL
    """)
    n = conn.execute("SELECT COUNT(*) FROM fact_posts").fetchone()[0]
    logger.info("fact_posts_loaded", rows=n)
    return n


def load_fact_comments(conn: DuckDBPyConnection) -> int:
    conn.execute("""
        INSERT OR IGNORE INTO fact_comments
        WITH post_lookup AS (
            SELECT fp.post_key, fp.external_id, dp.platform
            FROM   fact_posts   fp
            JOIN   dim_platform dp ON dp.platform_key = fp.platform_key
        )
        SELECT
            c.id                                                  AS comment_key,
            CAST(strftime(c.published_at::DATE, '%Y%m%d') AS INTEGER) AS date_key,
            dp.platform_key,
            dct.content_type_key,
            da.author_key,
            pl.post_key,
            c.external_id,
            c.id                                                  AS postgres_id,
            c.post_external_id,
            c.like_count,
            c.reply_count,
            c.depth,
            c.quality_score,
            c.is_usable,
            (c.text IS NOT NULL AND length(c.text) > 0)          AS has_text,
            CASE WHEN c.text IS NOT NULL THEN length(c.text) ELSE 0 END AS text_length,
            c.is_reply
        FROM pg.public.comments c
        JOIN  dim_platform     dp  ON dp.platform     = c.platform
        JOIN  dim_content_type dct ON dct.content_type = c.content_type
        LEFT JOIN (
            SELECT platform, author, author_key,
                   ROW_NUMBER() OVER (PARTITION BY platform, author ORDER BY effective_from DESC) AS rn
            FROM dim_author WHERE is_current = TRUE
        ) da ON da.platform = c.platform
            AND da.author   = COALESCE(c.author, '<unknown>')
            AND da.rn = 1
        LEFT JOIN post_lookup  pl  ON pl.external_id = c.post_external_id
                                  AND pl.platform    = c.platform
        WHERE c.published_at IS NOT NULL
    """)
    n = conn.execute("SELECT COUNT(*) FROM fact_comments").fetchone()[0]
    logger.info("fact_comments_loaded", rows=n)
    return n
