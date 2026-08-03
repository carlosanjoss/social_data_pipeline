"""
Queries analíticas de exemplo sobre o Star Schema.
Úteis para exploração, relatórios e validação do DW.
"""
from __future__ import annotations

from duckdb import DuckDBPyConnection


def posts_por_plataforma_dia(conn: DuckDBPyConnection) -> list[tuple]:
    return conn.execute("""
        SELECT
            dp.platform,
            dd.year,
            dd.month,
            COUNT(*)                       AS total_posts,
            SUM(fp.like_count)             AS total_likes,
            AVG(fp.quality_score)          AS avg_quality,
            SUM(fp.has_text::INTEGER)      AS posts_com_texto
        FROM  fact_posts fp
        JOIN  dim_platform dp ON dp.platform_key = fp.platform_key
        JOIN  dim_date     dd ON dd.date_key      = fp.date_key
        GROUP BY dp.platform, dd.year, dd.month
        ORDER BY dp.platform, dd.year, dd.month
    """).fetchall()


def top_autores_por_plataforma(conn: DuckDBPyConnection, n: int = 10) -> list[tuple]:
    return conn.execute(f"""
        SELECT
            dp.platform,
            da.author,
            COUNT(*)               AS total_posts,
            SUM(fp.like_count)     AS total_likes,
            AVG(fp.quality_score)  AS avg_quality
        FROM  fact_posts fp
        JOIN  dim_platform dp ON dp.platform_key = fp.platform_key
        JOIN  dim_author   da ON da.author_key   = fp.author_key
        GROUP BY dp.platform, da.author
        ORDER BY total_posts DESC
        LIMIT {n}
    """).fetchall()


def distribuicao_qualidade(conn: DuckDBPyConnection) -> list[tuple]:
    return conn.execute("""
        SELECT
            dp.platform,
            'posts'                       AS tipo,
            COUNT(*)                      AS total,
            AVG(fp.quality_score)         AS avg_score,
            SUM(fp.is_usable::INTEGER)    AS utilizaveis,
            ROUND(100.0 * SUM(fp.is_usable::INTEGER) / COUNT(*), 1) AS pct_utilizavel
        FROM  fact_posts fp
        JOIN  dim_platform dp ON dp.platform_key = fp.platform_key
        GROUP BY dp.platform

        UNION ALL

        SELECT
            dp.platform,
            'comments',
            COUNT(*),
            AVG(fc.quality_score),
            SUM(fc.is_usable::INTEGER),
            ROUND(100.0 * SUM(fc.is_usable::INTEGER) / COUNT(*), 1)
        FROM  fact_comments fc
        JOIN  dim_platform dp ON dp.platform_key = fc.platform_key
        GROUP BY dp.platform
        ORDER BY platform, tipo
    """).fetchall()


def engajamento_por_dia_semana(conn: DuckDBPyConnection) -> list[tuple]:
    return conn.execute("""
        SELECT
            dd.weekday_name,
            dp.platform,
            COUNT(*)               AS total_posts,
            AVG(fp.like_count)     AS avg_likes,
            AVG(fp.comment_count)  AS avg_comments
        FROM  fact_posts fp
        JOIN  dim_date     dd ON dd.date_key      = fp.date_key
        JOIN  dim_platform dp ON dp.platform_key  = fp.platform_key
        GROUP BY dd.weekday, dd.weekday_name, dp.platform
        ORDER BY dd.weekday, dp.platform
    """).fetchall()


def top_subreddits(conn: DuckDBPyConnection, n: int = 20) -> list[tuple]:
    return conn.execute(f"""
        SELECT
            dl.location   AS subreddit,
            COUNT(*)      AS total_posts,
            AVG(fp.quality_score) AS avg_quality
        FROM  fact_posts fp
        JOIN  dim_platform dp ON dp.platform_key = fp.platform_key
        JOIN  dim_location dl ON dl.location_key = fp.location_key
        WHERE dp.platform = 'reddit'
        GROUP BY dl.location
        ORDER BY total_posts DESC
        LIMIT {n}
    """).fetchall()


def hierarquia_comentarios(conn: DuckDBPyConnection) -> list[tuple]:
    """Distribuição de profundidade de comentários por plataforma."""
    return conn.execute("""
        SELECT
            dp.platform,
            fc.is_reply,
            COUNT(*)          AS total,
            AVG(fc.depth)     AS avg_depth,
            AVG(fc.like_count) AS avg_likes
        FROM  fact_comments fc
        JOIN  dim_platform dp ON dp.platform_key = fc.platform_key
        GROUP BY dp.platform, fc.is_reply
        ORDER BY dp.platform, fc.is_reply
    """).fetchall()
