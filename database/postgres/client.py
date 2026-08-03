from __future__ import annotations

import psycopg
from psycopg import Connection

from config import settings, get_logger

logger = get_logger(__name__)

_conn: Connection | None = None


def get_conn() -> Connection:
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(settings.postgres_uri, autocommit=False)
        logger.info("postgres_connected", uri=_sanitize_uri(settings.postgres_uri))
    return _conn


def close_conn() -> None:
    global _conn
    if _conn and not _conn.closed:
        _conn.close()
        _conn = None
        logger.info("postgres_disconnected")


def _sanitize_uri(uri: str) -> str:
    if "@" in uri:
        return uri.split("@", 1)[-1]
    return uri
