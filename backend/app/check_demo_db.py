from decimal import Decimal

from app.database import get_connection
from app.init_demo_db import INSTRUMENTS
from app.repositories import (
    get_instrument_parameters,
    get_latest_snapshot,
    instrument_exists,
)


def main() -> None:
    with get_connection() as connection:
        snapshot = get_latest_snapshot(connection)

        if snapshot is None:
            raise RuntimeError("Нет опубликованного снапшота")

        print(
            "Снапшот:",
            snapshot["id"],
            snapshot["as_of_date"],
            snapshot["published_at"],
        )

        for isin, _ in INSTRUMENTS:
            exists = instrument_exists(connection, isin)

            parameters = get_instrument_parameters(
                connection,
                snapshot["id"],
                isin,
            )

            print(f"\n{isin}")
            print("Инструмент существует:", exists)

            if parameters is None:
                print("Параметры отсутствуют")
                continue

            print("Тип купона:", parameters["coupon_type"])
            print("Валюта:", parameters["currency"])
            print("Курс к рублю:", parameters["fx_to_rub"])
            print("Номинал:", Decimal(parameters["nominal"]))
            print(
                "Котировка с НКД, %:",
                Decimal(parameters["dirty_quote_percent"]),
            )


if __name__ == "__main__":
    main()
