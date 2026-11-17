from datetime import date

from app.database import get_connection


# Все значения учебные, не являются данными рыночного источника.
DEMO_DATE = date(2026, 10, 27)
INSTRUMENTS = [
    ("RU000A000008", "DEMO: фиксированный купон, RUB"),
    ("RU000A000016", "DEMO: плавающий купон, RUB"),
    ("RU000A000024", "DEMO: инструмент без параметров"),
    ("RU000A000032", "DEMO: фиксированный купон, USD"),
    ("RU000A000040", "DEMO: короткая облигация с фиксированным купоном, RUB"),
    ("RU000A000057", "DEMO: отсутствует дюрация"),
    ("RU000A000065", "DEMO: отсутствует частота купона"),
]

# isin, currency, nominal, dirty_quote_percent, modified_duration,
# convexity, coupon_type, coupon_payments_per_year
PARAMETERS = [
    ("RU000A000008", "RUB", "1000", "86.5798", "3.5255", "16.2622", "fixed", 2),
    ("RU000A000016", "RUB", "1000", "100.3000", None, None, "floating", 4),
    ("RU000A000032", "USD", "1000", "94.7579", "2.6760", "8.7779", "fixed", 2),
    ("RU000A000040", "RUB", "1000", "101.7833", "0.8880", "1.2158", "fixed", 2),
    ("RU000A000057", "RUB", "1000", "86.5798", None, "16.2622", "fixed", 2),
    ("RU000A000065", "RUB", "1000", "100.3000", None, None, "floating", None),
]


def initialize_demo_database() -> None:
    with get_connection() as connection:
        snapshot = connection.execute(
            """
            INSERT INTO snapshot_batches (as_of_date, status)
            VALUES (%s, 'LOADING')
            ON CONFLICT (as_of_date) DO NOTHING
            RETURNING id
            """,
            (DEMO_DATE,),
        ).fetchone()

        if snapshot is None:
            print(f"Набор за {DEMO_DATE} уже существует и не изменён.")
            return

        snapshot_id = snapshot["id"]
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO instruments (isin, name) VALUES (%s, %s)
                ON CONFLICT (isin) DO NOTHING
                """,
                INSTRUMENTS,
            )
            cursor.executemany(
                """
                INSERT INTO fx_rates (snapshot_id, currency, rub_per_unit)
                VALUES (%s, %s, %s)
                """,
                [(snapshot_id, "RUB", "1"), (snapshot_id, "USD", "90")],
            )
            cursor.executemany(
                """
                INSERT INTO instrument_parameters (
                    snapshot_id, isin, currency, nominal, dirty_quote_percent,
                    modified_duration, convexity, coupon_type,
                    coupon_payments_per_year
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [(snapshot_id, *parameters) for parameters in PARAMETERS],
            )

        connection.execute(
            """
            UPDATE snapshot_batches
            SET status = 'PUBLISHED', published_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (snapshot_id,),
        )

    print(f"Создан учебный набор {snapshot_id} за {DEMO_DATE}.")
    print(f"Инструментов: {len(INSTRUMENTS)}; наборов параметров: {len(PARAMETERS)}.")


if __name__ == "__main__":
    initialize_demo_database()
