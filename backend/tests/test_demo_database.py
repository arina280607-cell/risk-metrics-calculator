from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import init_demo_db
from app.database import get_connection
from app.main import app


URL = "/api/v1/calculations/dv01"


@pytest.fixture
def demo_client(postgres_schema):
    init_demo_db.initialize_demo_database()
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "isin, position, result",
    [
        ("RU000A000008", "86579.8", "-30.5166685998822"),
        ("RU000A000016", "100300", "-2.5075"),
        ("RU000A000032", "8528211", "-2281.7749646833155"),
        ("RU000A000040", "101783.3", "-9.0377382993193"),
    ],
)
def test_demo_calculations(demo_client, isin, position, result):
    response = demo_client.post(URL, json={"trades": [{"isin": isin, "quantity": 100}]})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert Decimal(data["results"][0]["position_value"]) == Decimal(position)
    assert Decimal(data["total_value"]) == Decimal(result)
    assert data["snapshot"]["as_of_date"] == str(init_demo_db.DEMO_DATE)
    assert data["snapshot"]["published_at"] is not None


@pytest.mark.parametrize(
    "isin, code",
    [
        ("RU000A000024", "PARAMETER_SNAPSHOT_NOT_FOUND"),
        ("RU000A000057", "MISSING_INSTRUMENT_PARAMETERS"),
        ("RU000A000065", "MISSING_INSTRUMENT_PARAMETERS"),
        ("RU000A000073", "INSTRUMENT_NOT_FOUND"),
    ],
)
def test_demo_data_errors(demo_client, isin, code):
    response = demo_client.post(
        URL,
        json={"trades": [
            {"isin": isin, "quantity": 100},
            {"isin": "RU000A000008", "quantity": 100},
        ]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PARTIAL_SUCCESS"
    assert data["results"][0]["error"]["code"] == code
    assert Decimal(data["total_value"]) == Decimal("-30.5166685998822")


def test_demo_can_be_loaded_twice(demo_client):
    with get_connection() as connection:
        original = connection.execute("SELECT * FROM snapshot_batches").fetchone()
    init_demo_db.initialize_demo_database()
    with get_connection() as connection:
        snapshots = connection.execute("SELECT * FROM snapshot_batches").fetchall()
        assert snapshots == [original]
        for table, count in [
            ("instruments", 7), ("fx_rates", 2), ("instrument_parameters", 6)
        ]:
            row = connection.execute(
                psycopg.sql.SQL("SELECT count(*) AS count FROM {}").format(
                    psycopg.sql.Identifier(table)
                )
            ).fetchone()
            assert row["count"] == count


def test_failed_demo_load_rolls_back(postgres_schema, monkeypatch):
    monkeypatch.setattr(
        init_demo_db,
        "PARAMETERS",
        [*init_demo_db.PARAMETERS,
         ("RU000A000024", "EUR", "1000", "95", "4", "20", "fixed", 2)],
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        init_demo_db.initialize_demo_database()

    with get_connection() as connection:
        assert connection.execute("SELECT count(*) AS count FROM snapshot_batches").fetchone()["count"] == 0
        assert connection.execute("SELECT count(*) AS count FROM instruments").fetchone()["count"] == 0


def test_currency_rate_comes_from_selected_snapshot(demo_client):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO snapshot_batches (id, as_of_date, status, published_at)
            VALUES (100, '2026-10-28', 'PUBLISHED', CURRENT_TIMESTAMP)
            """
        )
        connection.execute("INSERT INTO fx_rates VALUES (100, 'USD', 100)")
        connection.execute(
            """
            INSERT INTO instrument_parameters
            SELECT 100, isin, currency, nominal, dirty_quote_percent,
                   modified_duration, convexity, coupon_type, coupon_payments_per_year
            FROM instrument_parameters WHERE isin = 'RU000A000032'
            """
        )
    response = demo_client.post(
        URL, json={"trades": [{"isin": "RU000A000032", "quantity": 100}]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["snapshot"]["id"] == 100
    assert Decimal(data["results"][0]["position_value"]) == Decimal("9475790")
