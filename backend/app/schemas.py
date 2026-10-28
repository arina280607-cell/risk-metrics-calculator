from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from datetime import date

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.validators import is_valid_isin


class CalculationRequest(BaseModel):
    trades: list[Any] = Field(
        min_length=1,
        description="Список сделок для независимого расчёта",
        examples=[
            [
                {"isin": "RU000A000008", "quantity": 100},
                {"isin": "RU000A000008", "quantity": -10},
            ]
        ],
    )


class TradeInput(BaseModel):
    isin: str = Field(
        strict=True,
        description="ISIN облигации",
    )

    quantity: Decimal = Field(
        allow_inf_nan=False,
        description="Количество облигаций со знаком",
    )

    @field_validator("isin", mode="before")
    @classmethod
    def validate_isin(cls, value: Any) -> str:
        if value is None:
            raise PydanticCustomError(
                "REQUIRED",
                "Укажите ISIN",
            )

        if not isinstance(value, str):
            raise PydanticCustomError(
                "INVALID_TYPE",
                "ISIN должен быть строкой",
            )

        if not value.strip():
            raise PydanticCustomError(
                "REQUIRED",
                "Укажите ISIN",
            )

        if not is_valid_isin(value):
            raise PydanticCustomError(
                "INVALID_ISIN",
                "Неверный формат или контрольная цифра ISIN",
            )

        return value

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: Any) -> Decimal:
        if value is None:
            raise PydanticCustomError(
                "REQUIRED",
                "Укажите количество облигаций",
            )

        if type(value) not in (int, float, Decimal):
            raise PydanticCustomError(
                "INVALID_TYPE",
                "Количество облигаций должно быть числом",
            )

        quantity = Decimal(str(value))

        if not quantity.is_finite():
            raise PydanticCustomError(
                "INVALID_VALUE",
                "Количество облигаций должно быть конечным числом",
            )

        return quantity

class ErrorDetail(BaseModel):
    field: str
    code: str
    message: str


class ApiError(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class TradeSuccess(BaseModel):
    index: int = Field(ge=0)
    status: Literal["SUCCESS"] = "SUCCESS"

    isin: str
    quantity: Decimal

    position_value: Decimal = Field(allow_inf_nan=False)
    result_value: Decimal = Field(allow_inf_nan=False)

    duration_used: Decimal = Field(allow_inf_nan=False)
    convexity_used: Decimal = Field(allow_inf_nan=False)
    rate_shift_bps: Literal[1] = 1

    cache_hit: bool = False
    error: None = None


class TradeFailure(BaseModel):
    index: int = Field(ge=0)
    status: Literal["ERROR"] = "ERROR"

    result_value: None = None
    error: ApiError


TradeResult = Annotated[
    TradeSuccess | TradeFailure,
    Field(discriminator="status"),
]

class SnapshotInfo(BaseModel):
    version: str = Field(description="Версия использованного набора данных")
    as_of_date: date = Field(description="Дата рыночных данных")
    source: str = Field(description="Источник данных")

class CalculationResponse(BaseModel):
    calculation_id: UUID
    metric: Literal["DV01"] = "DV01"

    status: Literal["SUCCESS", "PARTIAL_SUCCESS", "ERROR"]
    result_currency: Literal["RUB"] = "RUB"

    results: list[TradeResult] = Field(min_length=1)

    total_value: Decimal | None = Field(
        allow_inf_nan=False,
        description=(
            "Алгебраическая сумма успешных результатов. "
            "Если успешных результатов нет — null."
        ),
    )
    snapshot: SnapshotInfo | None = Field(
        default=None,
        description="Набор данных, выбранный для расчёта",
    )


class ErrorResponse(BaseModel):
    error: ApiError
