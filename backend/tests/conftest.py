from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql

from app.database import get_connection


@pytest.fixture
def postgres_schema(monkeypatch):
    # Каждый тест работает в своей временной схеме, не меняя рабочие таблицы.
    name = f"test_{uuid4().hex}"
    with get_connection() as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))

    monkeypatch.setenv("PGOPTIONS", f"-c search_path={name}")
    try:
        with get_connection() as connection:
            connection.autocommit = True
            schema = Path(__file__).resolve().parents[1] / "schema.sql"
            connection.execute(schema.read_text(encoding="utf-8"))
        yield
    finally:
        with get_connection() as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name))
            )
