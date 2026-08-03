"""
Creates all PostgreSQL tables defined in schema.sql.

Run:
    python -m database.postgres.setup
"""
from pathlib import Path

from config import setup_logging, get_logger
from .client import get_conn, close_conn

logger = get_logger(__name__)

SCHEMA_FILE = Path(__file__).parent / "schema.sql"
SCOPE_FILE = Path(__file__).parent / "enforce_final_scope.sql"


def create_tables() -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    scope_sql = SCOPE_FILE.read_text(encoding="utf-8")
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(scope_sql)
    conn.commit()
    logger.info(
        "postgres_schema_and_scope_applied",
        schema_file=str(SCHEMA_FILE),
        scope_file=str(SCOPE_FILE),
    )


if __name__ == "__main__":
    setup_logging()
    create_tables()
    close_conn()
    print("Schema aplicado com sucesso.")
