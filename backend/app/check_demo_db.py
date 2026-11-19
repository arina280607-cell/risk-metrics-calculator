from contextlib import closing
from decimal import Decimal

from app.database import get_connection
from app.repositories import (
    get_instrument_parameters,
    get_latest_snapshot,
    instrument_exists,
)


def main() -> None:
    with closing(get_connection()) as connection:
        snapshot = get_latest_snapshot(connection)

        if snapshot is None:
            raise RuntimeError("Нет опубликованного снапшота")

        print(
            "Снапшот:",
            snapshot["version"],
            snapshot["as_of_date"],
            snapshot["source"],
        )

        for isin in (
            "RU000A000008",
            "RU000A000016",
            "RU000A000024",
        ):
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
            print("Номинал:", Decimal(parameters["nominal"]))
            print(
                "Котировка с НКД, %:",
                Decimal(parameters["dirty_quote_percent"]),
            )


if __name__ == "__main__":
    main()