from __future__ import annotations

from pathlib import Path

import duckdb
from duckdb import DuckDBPyConnection

from config import settings, get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "radar_odio.duckdb"

_conn: DuckDBPyConnection | None = None


def get_conn() -> DuckDBPyConnection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(str(DB_PATH))
        _attach_postgres(_conn)
        logger.info("duckdb_connected", path=str(DB_PATH))
    return _conn


def close_conn() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def _attach_postgres(conn: DuckDBPyConnection) -> None:
    """Anexa o PostgreSQL como fonte de dados nativa do DuckDB."""
    conn.execute("INSTALL postgres; LOAD postgres;")
    # Converte URI psycopg3 para formato DSN do DuckDB
    pg_dsn = _uri_to_dsn(settings.postgres_uri)
    conn.execute(f"ATTACH IF NOT EXISTS '{pg_dsn}' AS pg (TYPE POSTGRES, READ_ONLY);")
    logger.info("postgres_attached", dsn=pg_dsn.split("password=")[0])


def _uri_to_dsn(uri: str) -> str:
    """postgresql://user:pass@host:port/db  →  host=... dbname=..."""
    # e.g. postgresql://radar:admin123@localhost:5433/radar_odio
    from urllib.parse import urlparse
    p = urlparse(uri)
    return (
        f"host={p.hostname} port={p.port or 5432} "
        f"dbname={p.path.lstrip('/')} "
        f"user={p.username} password={p.password}"
    )


def apply_schema() -> None:
    schema_sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    conn = get_conn()
    conn.execute(schema_sql)
    logger.info("duckdb_schema_applied")
