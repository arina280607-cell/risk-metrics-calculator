import pytest

from app import database


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    test_db_path = tmp_path / "isolated_test.db"
    monkeypatch.setenv("DATABASE_PATH", str(test_db_path))
    monkeypatch.setattr(database, "DATABASE_PATH", test_db_path)
    yield test_db_path
