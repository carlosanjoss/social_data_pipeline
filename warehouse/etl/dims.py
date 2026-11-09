"""
Carga de todas as tabelas de dimensão.
"""
from __future__ import annotations

from datetime import date, timedelta

from duckdb import DuckDBPyConnection

from config import get_logger

logger = get_logger(__name__)


# ── dim_date ──────────────────────────────────────────────────────────────────

def load_dim_date(conn: DuckDBPyConnection, start: date | None = None) -> int:
    """Gera spine de datas de start até hoje."""
    WEEKDAY_NAMES = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    MONTH_NAMES   = ["","January","February","March","April","May","June",
                     "July","August","September","October","November","December"]

    if start is None:
        row = conn.execute(
            "SELECT MIN(published_at::DATE) FROM pg.public.posts "
            "WHERE published_at IS NOT NULL"
        ).fetchone()
        start = row[0] if row and row[0] else date(2019, 1, 1)
    end = date(2030, 12, 31)

    rows = []
    d = start
    while d <= end:
        rows.append((
            int(d.strftime("%Y%m%d")),
            d,
            d.year,
            (d.month - 1) // 3 + 1,
            d.month,
            MONTH_NAMES[d.month],
            d.isocalendar()[1],
            d.day,
            d.weekday(),
            WEEKDAY_NAMES[d.weekday()],
            d.weekday() >= 5,
        ))
        d += timedelta(days=1)

    conn.executemany(
        """INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    logger.info("dim_date_loaded", rows=len(rows))
    return len(rows)


# ── dim_platform ──────────────────────────────────────────────────────────────

def load_dim_platform(conn: DuckDBPyConnection) -> int:
    rows = [
        (1, "reddit",   "Reddit"),
        (2, "twitter",  "Twitter / X"),
        (3, "youtube",  "YouTube"),
        (4, "facebook", "Facebook"),
        (5, "tiktok",   "TikTok"),
        (6, "whatsapp", "WhatsApp"),
        (7, "telegram", "Telegram"),
        (8, "instagram","Instagram"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO dim_platform VALUES (?,?,?)", rows
    )
    logger.info("dim_platform_loaded", rows=len(rows))
    return len(rows)


# ── dim_content_type ──────────────────────────────────────────────────────────

def load_dim_content_type(conn: DuckDBPyConnection) -> int:
    rows = [
        (1, "post",    True,  False),
        (2, "tweet",   True,  False),
        (3, "reply",   True,  True),
        (4, "video",   True,  False),
        (5, "comment", False, True),
        (6, "message", True,  False),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO dim_content_type VALUES (?,?,?,?)", rows
    )
    logger.info("dim_content_type_loaded", rows=len(rows))
    return len(rows)


# ── dim_location ──────────────────────────────────────────────────────────────

def load_dim_location(conn: DuckDBPyConnection) -> int:
    conn.execute("""
        INSERT OR IGNORE INTO dim_location (platform, location)
        SELECT DISTINCT
            p.platform,
            COALESCE(r.subreddit, y.channel_id, fb.page_slug, tw.group_name,
                     wa.group_id, tg.group_id) AS location
        FROM   pg.public.posts      p
        LEFT JOIN pg.public.reddit_posts   r  ON r.post_id  = p.id
        LEFT JOIN pg.public.youtube_videos y  ON y.post_id  = p.id
        LEFT JOIN pg.public.facebook_posts fb ON fb.post_id = p.id
        LEFT JOIN pg.public.twitter_tweets tw ON tw.post_id = p.id
        LEFT JOIN pg.public.whatsapp_messages wa ON wa.post_id = p.id
        LEFT JOIN pg.public.telegram_messages tg ON tg.post_id = p.id
        WHERE COALESCE(r.subreddit, y.channel_id, fb.page_slug, tw.group_name,
                       wa.group_id, tg.group_id) IS NOT NULL
    """)
    n = conn.execute("SELECT COUNT(*) FROM dim_location").fetchone()[0]
    logger.info("dim_location_loaded", rows=n)
    return n


# ── dim_author (SCD Type 2) ───────────────────────────────────────────────────

def load_dim_author(conn: DuckDBPyConnection) -> int:
    """
    SCD Type 2:
    - Novos autores → INSERT com effective_from=hoje, effective_to=NULL
    - Autores já existentes com is_current=TRUE → sem alteração (versão atual mantida)
    Ao re-executar com novos dados, autores novos ganham nova linha;
    autores existentes continuam com sua versão atual intacta.
    """
    today = date.today().isoformat()

    conn.execute(f"""
        INSERT OR IGNORE INTO dim_author (platform, author, author_id, effective_from, effective_to, is_current)

        SELECT DISTINCT
            platform,
            COALESCE(author, '<unknown>') AS author,
            author_id,
            DATE '{today}' AS effective_from,
            NULL           AS effective_to,
            TRUE           AS is_current
        FROM pg.public.posts
        WHERE author IS NOT NULL
          AND author != 'nan'

        UNION

        SELECT DISTINCT
            platform,
            COALESCE(author, '<unknown>') AS author,
            author_id,
            DATE '{today}',
            NULL,
            TRUE
        FROM pg.public.comments
        WHERE author IS NOT NULL
          AND author != 'nan'
    """)
    n = conn.execute("SELECT COUNT(*) FROM dim_author").fetchone()[0]
    logger.info("dim_author_loaded", rows=n)
    return n
