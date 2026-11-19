from contextlib import closing

from app.database import DATABASE_PATH, get_connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    isin TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_batches (
    id INTEGER PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    as_of_date TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('LOADING', 'PUBLISHED')
    )
);

CREATE TABLE IF NOT EXISTS instrument_parameters (
    snapshot_id INTEGER NOT NULL,
    isin TEXT NOT NULL,

    currency TEXT NOT NULL,
    nominal TEXT NOT NULL,
    dirty_quote_percent TEXT NOT NULL,
    fx_to_rub TEXT NOT NULL,

    modified_duration TEXT,
    convexity TEXT,

    coupon_type TEXT NOT NULL CHECK (
        coupon_type IN ('fixed', 'floating')
    ),
    coupon_payments_per_year INTEGER,

    PRIMARY KEY (snapshot_id, isin),

    FOREIGN KEY (snapshot_id)
        REFERENCES snapshot_batches(id),

    FOREIGN KEY (isin)
        REFERENCES instruments(isin)
);
"""


def initialize_demo_database() -> None:
    with closing(get_connection()) as connection:
        connection.executescript(SCHEMA)

        with connection:
            connection.executemany(
                """
                INSERT INTO instruments (isin, name)
                VALUES (?, ?)
                ON CONFLICT(isin) DO NOTHING
                """,
                [
                    (
                        "RU000A000008",
                        "DEMO: облигация с фиксированным купоном",
                    ),
                    (
                        "RU000A000016",
                        "DEMO: облигация с плавающим купоном",
                    ),
                    (
                        "RU000A000024",
                        "DEMO: инструмент без параметров",
                    ),
                ],
            )

            existing = connection.execute(
                """
                SELECT id
                FROM snapshot_batches
                WHERE version = ?
                """,
                ("demo-v1",),
            ).fetchone()

            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO snapshot_batches (
                        version,
                        as_of_date,
                        source,
                        status
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "demo-v1",
                        "2026-10-27",
                        "DEMO",
                        "LOADING",
                    ),
                )

                snapshot_id = cursor.lastrowid

                connection.executemany(
                    """
                    INSERT INTO instrument_parameters (
                        snapshot_id,
                        isin,
                        currency,
                        nominal,
                        dirty_quote_percent,
                        fx_to_rub,
                        modified_duration,
                        convexity,
                        coupon_type,
                        coupon_payments_per_year
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_id,
                            "RU000A000008",
                            "RUB",
                            "1000",
                            "95",
                            "1",
                            "4",
                            "20",
                            "fixed",
                            2,
                        ),
                        (
                            snapshot_id,
                            "RU000A000016",
                            "RUB",
                            "1000",
                            "95",
                            "1",
                            None,
                            None,
                            "floating",
                            4,
                        ),
                    ],
                )

                connection.execute(
                    """
                    UPDATE snapshot_batches
                    SET status = 'PUBLISHED'
                    WHERE id = ?
                    """,
                    (snapshot_id,),
                )

        instrument_count = connection.execute(
            "SELECT COUNT(*) FROM instruments"
        ).fetchone()[0]

        parameter_count = connection.execute(
            "SELECT COUNT(*) FROM instrument_parameters"
        ).fetchone()[0]

    print(f"Демонстрационная БД: {DATABASE_PATH}")
    print(f"Инструментов: {instrument_count}")
    print(f"Наборов параметров: {parameter_count}")


if __name__ == "__main__":
    initialize_demo_database()