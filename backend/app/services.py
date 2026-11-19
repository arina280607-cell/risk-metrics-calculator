import sqlite3
from contextlib import closing
from decimal import Decimal, DecimalException
from uuid import uuid4

from pydantic import ValidationError

from app.calculator import calculate_dv01
from app.database import get_connection
from app.repositories import (
    get_instrument_parameters,
    get_latest_snapshot,
    instrument_exists,
)
from app.schemas import (
    ApiError,
    CalculationRequest,
    CalculationResponse,
    ErrorDetail,
    TradeFailure,
    TradeInput,
    TradeResult,
    TradeSuccess,
    SnapshotInfo,
)

def make_error_detail(error: dict) -> ErrorDetail:
    field = ".".join(str(part) for part in error["loc"]) or "trade"
    error_type = error["type"]

    if error_type == "missing":
        code = "REQUIRED"
        message = "Обязательное поле отсутствует"

    elif error_type in ("model_type", "model_attributes_type"):
        code = "INVALID_TYPE"
        message = "Сделка должна быть JSON-объектом"

    elif error_type in (
        "REQUIRED",
        "INVALID_TYPE",
        "INVALID_ISIN",
        "INVALID_VALUE",
    ):
        code = error_type
        message = error["msg"]

    else:
        code = "INVALID_VALUE"
        message = "Недопустимое значение поля"

    return ErrorDetail(
        field=field,
        code=code,
        message=message,
    )

class TradeCalculationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def read_decimal(
    parameters: sqlite3.Row,
    field: str,
) -> Decimal:
    value = parameters[field]

    if value is None:
        raise TradeCalculationError(
            "MISSING_INSTRUMENT_PARAMETERS",
            f"Отсутствует параметр: {field}",
        )

    try:
        number = Decimal(value)
    except (DecimalException, ValueError, TypeError):
        raise TradeCalculationError(
            "INVALID_INSTRUMENT_PARAMETERS",
            f"Некорректный параметр: {field}",
        ) from None

    if not number.is_finite():
        raise TradeCalculationError(
            "INVALID_INSTRUMENT_PARAMETERS",
            f"Параметр должен быть конечным числом: {field}",
        )

    return number


def calculate_trade(
    connection: sqlite3.Connection,
    snapshot_id: int | None,
    index: int,
    trade: TradeInput,
) -> TradeSuccess:
    if not instrument_exists(connection, trade.isin):
        raise TradeCalculationError(
            "INSTRUMENT_NOT_FOUND",
            "Инструмент с указанным ISIN не найден",
        )

    if snapshot_id is None:
        raise TradeCalculationError(
            "PARAMETER_SNAPSHOT_NOT_FOUND",
            "Нет опубликованного набора данных",
        )

    parameters = get_instrument_parameters(
        connection,
        snapshot_id,
        trade.isin,
    )

    if parameters is None:
        raise TradeCalculationError(
            "PARAMETER_SNAPSHOT_NOT_FOUND",
            "В выбранном снапшоте нет параметров инструмента",
        )

    coupon_type = parameters["coupon_type"]

    if coupon_type not in ("fixed", "floating"):
        raise TradeCalculationError(
            "INVALID_INSTRUMENT_PARAMETERS",
            "Неизвестный тип купона",
        )

    is_floating = coupon_type == "floating"

    if is_floating and parameters["coupon_payments_per_year"] is None:
        raise TradeCalculationError(
            "MISSING_INSTRUMENT_PARAMETERS",
            "Не указано число купонных выплат в год",
        )

    result = calculate_dv01(
        quantity=trade.quantity,
        nominal=read_decimal(parameters, "nominal"),
        dirty_quote_percent=read_decimal(
            parameters, "dirty_quote_percent"
        ),
        fx=read_decimal(parameters, "fx_to_rub"),
        modified_duration=(
            None
            if is_floating
            else read_decimal(parameters, "modified_duration")
        ),
        convexity=(
            None
            if is_floating
            else read_decimal(parameters, "convexity")
        ),
        is_floating=is_floating,
        coupon_payments_per_year=parameters[
            "coupon_payments_per_year"
        ],
    )

    return TradeSuccess(
        index=index,
        isin=trade.isin,
        quantity=trade.quantity,
        position_value=result.position_value,
        result_value=result.result_value,
        duration_used=result.duration_used,
        convexity_used=result.convexity_used,
        cache_hit=False,
    )

def process_calculation(
    request: CalculationRequest,
) -> CalculationResponse:
    results: list[TradeResult] = []

    with closing(get_connection()) as connection:
        connection.execute("BEGIN")

        snapshot = get_latest_snapshot(connection)
        snapshot_info = (
            SnapshotInfo(
                version=snapshot["version"],
                as_of_date=snapshot["as_of_date"],
                source=snapshot["source"],
            )
            if snapshot is not None
            else None
        )
        snapshot_id = snapshot["id"] if snapshot is not None else None

        for index, raw_trade in enumerate(request.trades):
            try:
                trade = TradeInput.model_validate(raw_trade)

            except ValidationError as exc:
                results.append(
                    TradeFailure(
                        index=index,
                        error=ApiError(
                            code="VALIDATION_ERROR",
                            message="Некорректные данные сделки",
                            details=[
                                make_error_detail(error)
                                for error in exc.errors()
                            ],
                        ),
                    )
                )
                continue

            try:
                result = calculate_trade(
                    connection,
                    snapshot_id,
                    index,
                    trade,
                )

            except TradeCalculationError as exc:
                result = TradeFailure(
                    index=index,
                    error=ApiError(
                        code=exc.code,
                        message=str(exc),
                    ),
                )

            except ValidationError:
                result = TradeFailure(
                    index=index,
                    error=ApiError(
                        code="CALCULATION_ERROR",
                        message="Не удалось сформировать результат расчёта",
                    ),
                )

            except ValueError as exc:
                result = TradeFailure(
                    index=index,
                    error=ApiError(
                        code="INVALID_INSTRUMENT_PARAMETERS",
                        message=str(exc),
                    ),
                )

            except DecimalException:
                result = TradeFailure(
                    index=index,
                    error=ApiError(
                        code="CALCULATION_ERROR",
                        message="Ошибка числового вычисления",
                    ),
                )

            results.append(result)

    successful_results = [
        result
        for result in results
        if isinstance(result, TradeSuccess)
    ]

    if not successful_results:
        status = "ERROR"
        total_value = None
    else:
        status = (
            "SUCCESS"
            if len(successful_results) == len(results)
            else "PARTIAL_SUCCESS"
        )

        total_value = sum(
            (result.result_value for result in successful_results),
            start=Decimal("0"),
        )

    return CalculationResponse(
        calculation_id=uuid4(),
        status=status,
        results=results,
        total_value=total_value,
        snapshot=snapshot_info,
    )