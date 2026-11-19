import sqlite3


def get_latest_snapshot(
    connection: sqlite3.Connection,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, version, as_of_date, source
        FROM snapshot_batches
        WHERE status = 'PUBLISHED'
        ORDER BY as_of_date DESC, id DESC
        LIMIT 1
        """
    ).fetchone()


def instrument_exists(
    connection: sqlite3.Connection,
    isin: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM instruments
        WHERE isin = ?
        """,
        (isin,),
    ).fetchone()

    return row is not None


def get_instrument_parameters(
    connection: sqlite3.Connection,
    snapshot_id: int,
    isin: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            currency,
            nominal,
            dirty_quote_percent,
            fx_to_rub,
            modified_duration,
            convexity,
            coupon_type,
            coupon_payments_per_year
        FROM instrument_parameters
        WHERE snapshot_id = ? AND isin = ?
        """,
        (snapshot_id, isin),
    ).fetchone()