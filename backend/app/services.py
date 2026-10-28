from uuid import uuid4

from pydantic import ValidationError

from app.schemas import (
    ApiError,
    CalculationRequest,
    CalculationResponse,
    ErrorDetail,
    TradeFailure,
    TradeInput,
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

def process_calculation(
    request: CalculationRequest,
) -> CalculationResponse:
    results: list[TradeFailure] = []

    for index, raw_trade in enumerate(request.trades):
        try:
            TradeInput.model_validate(raw_trade)

        except ValidationError as exc:
            details = [
                make_error_detail(error)
                for error in exc.errors()
            ]

            results.append(
                TradeFailure(
                    index=index,
                    error=ApiError(
                        code="VALIDATION_ERROR",
                        message="Некорректные данные сделки",
                        details=details,
                    ),
                )
            )
            continue

        # получение параметров и расчёт ещё не подключены.
        results.append(
            TradeFailure(
                index=index,
                error=ApiError(
                    code="CALCULATION_NOT_READY",
                    message="Расчёт риск-метрики ещё не подключён",
                ),
            )
        )

    return CalculationResponse(
        calculation_id=uuid4(),
        status="ERROR",
        results=results,
        total_value=None,
    )