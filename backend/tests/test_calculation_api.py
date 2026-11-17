from contextlib import closing
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


URL = "/api/v1/calculations/dv01"

FIXED_ISIN = "RU000A000008"
FLOATING_ISIN = "RU000A000016"
NO_PARAMETERS_ISIN = "RU000A000024"


@pytest.fixture
def client(postgres_schema):
    with closing(database.get_connection()) as connection:
        with connection:
            connection.cursor().executemany(
                """
                INSERT INTO instruments (isin, name)
                VALUES (%s, %s)
                """,
                [
                    (FIXED_ISIN, "TEST fixed"),
                    (FLOATING_ISIN, "TEST floating"),
                    (NO_PARAMETERS_ISIN, "TEST without parameters"),
                ],
            )

            connection.execute(
                """
                INSERT INTO snapshot_batches
                    (id, as_of_date, status, published_at)
                VALUES
                    (1, '2026-10-27', 'PUBLISHED', '2026-10-28T08:00:00Z')
                """
            )

            connection.execute(
                "INSERT INTO fx_rates VALUES (1, 'RUB', 1)"
            )

            connection.cursor().executemany(
                """
                INSERT INTO instrument_parameters (
                    snapshot_id,
                    isin,
                    currency,
                    nominal,
                    dirty_quote_percent,
                    modified_duration,
                    convexity,
                    coupon_type,
                    coupon_payments_per_year
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        1, FIXED_ISIN, "RUB",
                        "1000", "95",
                        "4", "20", "fixed", 2,
                    ),
                    (
                        1, FLOATING_ISIN, "RUB",
                        "1000", "95",
                        None, None, "floating", 4,
                    ),
                ],
            )

    with TestClient(app) as test_client:
        yield test_client


def send_trades(client, trades):
    response = client.post(URL, json={"trades": trades})
    assert response.status_code == 200, response.text
    return response.json()


def test_successful_trades_and_snapshot(client):
    data = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": 100},
            {"isin": FLOATING_ISIN, "quantity": 100},
        ],
    )

    assert data["status"] == "SUCCESS"
    assert data["snapshot"] == {
        "id": 1,
        "as_of_date": "2026-10-27",
        "published_at": "2026-10-28T08:00:00Z",
    }

    results = data["results"]
    assert len(results) == 2
    assert [item["index"] for item in results] == [0, 1]
    assert all(item["status"] == "SUCCESS" for item in results)

    assert Decimal(results[0]["position_value"]) == Decimal("95000")
    assert Decimal(results[0]["result_value"]) == Decimal("-37.9905")
    assert Decimal(results[1]["result_value"]) == Decimal("-2.375")
    assert Decimal(data["total_value"]) == Decimal("-40.3655")


def test_missing_parameters_do_not_break_other_trades(client):
    data = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": 100},
            {"isin": NO_PARAMETERS_ISIN, "quantity": 100},
            {"isin": FLOATING_ISIN, "quantity": 100},
        ],
    )

    assert data["status"] == "PARTIAL_SUCCESS"
    assert [item["index"] for item in data["results"]] == [0, 1, 2]
    assert [item["status"] for item in data["results"]] == [
        "SUCCESS", "ERROR", "SUCCESS",
    ]

    failed = data["results"][1]
    assert failed["result_value"] is None
    assert failed["error"]["code"] == "PARAMETER_SNAPSHOT_NOT_FOUND"
    assert Decimal(data["total_value"]) == Decimal("-40.3655")


def test_all_failed_returns_null_total(client):
    data = send_trades(
        client,
        [{"isin": NO_PARAMETERS_ISIN, "quantity": 100}],
    )

    assert data["status"] == "ERROR"
    assert data["total_value"] is None
    assert data["results"][0]["status"] == "ERROR"


def test_opposite_positions_cancel_out(client):
    data = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": 100},
            {"isin": FIXED_ISIN, "quantity": -100},
        ],
    )

    assert data["status"] == "SUCCESS"
    assert len(data["results"]) == 2
    assert Decimal(data["results"][0]["result_value"]) == Decimal("-37.9905")
    assert Decimal(data["results"][1]["result_value"]) == Decimal("37.9905")
    assert Decimal(data["total_value"]) == Decimal("0")


def test_invalid_trade_does_not_break_valid_trade(client):
    data = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": "not-a-number"},
            {"isin": FIXED_ISIN, "quantity": 100},
        ],
    )

    assert data["status"] == "PARTIAL_SUCCESS"
    assert data["results"][0]["status"] == "ERROR"
    assert data["results"][0]["error"]["code"] == "VALIDATION_ERROR"
    assert data["results"][1]["status"] == "SUCCESS"
    assert Decimal(data["total_value"]) == Decimal("-37.9905")


def test_latest_published_snapshot_is_used(client):
    with closing(database.get_connection()) as connection:
        with connection:
            connection.cursor().executemany(
                """
                INSERT INTO snapshot_batches
                    (id, as_of_date, status, published_at)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (2, "2026-10-28", "PUBLISHED", "2026-10-29T08:00:00Z"),
                    (3, "2026-10-29", "LOADING", None),
                ],
            )

            connection.execute("INSERT INTO fx_rates VALUES (2, 'RUB', 1)")

            connection.execute(
                """
                INSERT INTO instrument_parameters (
                    snapshot_id,
                    isin,
                    currency,
                    nominal,
                    dirty_quote_percent,
                    modified_duration,
                    convexity,
                    coupon_type,
                    coupon_payments_per_year
                )
                VALUES (
                    2, %s, 'RUB', '1000', '100',
                    '4', '20', 'fixed', 2
                )
                """,
                (FIXED_ISIN,),
            )

    data = send_trades(
        client,
        [{"isin": FIXED_ISIN, "quantity": 100}],
    )

    assert data["status"] == "SUCCESS"
    assert data["snapshot"]["id"] == 2
    assert data["snapshot"]["as_of_date"] == "2026-10-28"
    assert Decimal(data["results"][0]["position_value"]) == Decimal("100000")
    assert Decimal(data["total_value"]) == Decimal("-39.99")


def test_no_published_snapshot(client):
    with closing(database.get_connection()) as connection:
        with connection:
            connection.execute(
                "UPDATE snapshot_batches SET status = 'LOADING'"
            )

    data = send_trades(
        client,
        [{"isin": FIXED_ISIN, "quantity": 100}],
    )

    assert data["status"] == "ERROR"
    assert data["snapshot"] is None
    assert data["total_value"] is None
    assert (
        data["results"][0]["error"]["code"]
        == "PARAMETER_SNAPSHOT_NOT_FOUND"
    )

def test_total_after_editing_one_trade(client):
    first = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": 100},
            {"isin": FLOATING_ISIN, "quantity": 100},
        ],
    )

    assert first["status"] == "SUCCESS"
    assert Decimal(first["total_value"]) == Decimal("-40.3655")

    updated = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": 200},
            {"isin": FLOATING_ISIN, "quantity": 100},
        ],
    )

    assert updated["status"] == "SUCCESS"
    assert Decimal(updated["results"][0]["result_value"]) == Decimal("-75.981")
    assert Decimal(updated["results"][1]["result_value"]) == Decimal("-2.375")
    assert Decimal(updated["total_value"]) == Decimal("-78.356")

    invalid = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": "ошибка"},
            {"isin": FLOATING_ISIN, "quantity": 100},
        ],
    )

    assert invalid["status"] == "PARTIAL_SUCCESS"
    assert invalid["results"][0]["status"] == "ERROR"
    assert Decimal(invalid["total_value"]) == Decimal("-2.375")

    remaining = send_trades(
        client,
        [{"isin": FLOATING_ISIN, "quantity": 100}],
    )

    assert remaining["status"] == "SUCCESS"
    assert len(remaining["results"]) == 1
    assert Decimal(remaining["total_value"]) == Decimal("-2.375")

@pytest.mark.parametrize("quantity", [10.2, -0.5])
def test_fractional_quantity_is_rejected(client, quantity):
    data = send_trades(
        client,
        [
            {"isin": FIXED_ISIN, "quantity": quantity},
            {"isin": FLOATING_ISIN, "quantity": 100},
        ],
    )

    assert data["status"] == "PARTIAL_SUCCESS"

    failed = data["results"][0]
    assert failed["status"] == "ERROR"
    assert failed["error"]["code"] == "VALIDATION_ERROR"
    assert any(
        detail["field"] == "quantity"
        and detail["code"] == "INVALID_VALUE"
        and detail["message"]
        == "Количество облигаций должно быть целым числом"
        for detail in failed["error"]["details"]
    )

    assert data["results"][1]["status"] == "SUCCESS"
    assert Decimal(data["total_value"]) == Decimal("-2.375")


@pytest.mark.parametrize("quantity", [10, 10.0, -10, 0])
def test_integer_quantity_is_accepted(client, quantity):
    data = send_trades(
        client,
        [{"isin": FLOATING_ISIN, "quantity": quantity}],
    )

    assert data["status"] == "SUCCESS"
    assert data["results"][0]["status"] == "SUCCESS"

    expected = Decimal(str(quantity)) * Decimal("-0.02375")
    assert Decimal(data["total_value"]) == expected
