from psycopg import Connection


def get_latest_snapshot(connection: Connection) -> dict | None:
    return connection.execute(
        """
        SELECT id, as_of_date, published_at
        FROM snapshot_batches
        WHERE status = 'PUBLISHED'
        ORDER BY as_of_date DESC, id DESC
        LIMIT 1
        """
    ).fetchone()


def instrument_exists(connection: Connection, isin: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM instruments WHERE isin = %s",
        (isin,),
    ).fetchone()
    return row is not None


def get_instrument_parameters(
    connection: Connection,
    snapshot_id: int,
    isin: str,
) -> dict | None:
    return connection.execute(
        """
        SELECT
            p.currency,
            p.nominal,
            p.dirty_quote_percent,
            f.rub_per_unit AS fx_to_rub,
            p.modified_duration,
            p.convexity,
            p.coupon_type,
            p.coupon_payments_per_year
        FROM instrument_parameters p
        JOIN fx_rates f
            ON f.snapshot_id = p.snapshot_id AND f.currency = p.currency
        WHERE p.snapshot_id = %s AND p.isin = %s
        """,
        (snapshot_id, isin),
    ).fetchone()
