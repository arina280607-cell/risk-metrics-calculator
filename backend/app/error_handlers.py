from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import ApiError, ErrorDetail, ErrorResponse


async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()

    if not await request.body():
        status_code = 400
        error = ApiError(
            code="INVALID_REQUEST",
            message="Отсутствует тело запроса",
        )

    elif any(item["type"] == "json_invalid" for item in errors):
        status_code = 400
        error = ApiError(
            code="INVALID_REQUEST",
            message="Некорректный JSON",
        )

    else:
        status_code = 422
        details = []

        for item in errors:
            location = item["loc"]

            if location and location[0] == "body":
                location = location[1:]

            field = ".".join(str(part) for part in location) or "body"

            if item["type"] == "missing":
                code = "REQUIRED"
                message = "Обязательное поле отсутствует"

            elif field == "trades" and item["type"] == "too_short":
                code = "EMPTY_LIST"
                message = "Добавьте хотя бы одну сделку"

            elif item["type"] in (
                "list_type",
                "model_type",
                "model_attributes_type",
            ):
                code = "INVALID_TYPE"
                message = "Неверный тип данных"

            else:
                code = "INVALID_VALUE"
                message = "Недопустимое значение"

            details.append(
                ErrorDetail(
                    field=field,
                    code=code,
                    message=message,
                )
            )

        error = ApiError(
            code="VALIDATION_ERROR",
            message="Некорректная структура запроса",
            details=details,
        )

    response = ErrorResponse(error=error)

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
    )