from dataclasses import dataclass
from decimal import Decimal


ONE_BP = Decimal("0.0001")


@dataclass(frozen=True)
class CalculationResult:
    position_value: Decimal
    result_value: Decimal
    duration_used: Decimal
    convexity_used: Decimal


def require_finite(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise ValueError(f"{name}: ожидается Decimal")

    if not value.is_finite():
        raise ValueError(f"{name}: число должно быть конечным")


def calculate_dv01(
    *,
    quantity: Decimal,
    nominal: Decimal,
    dirty_quote_percent: Decimal,
    fx: Decimal,
    modified_duration: Decimal | None = None,
    convexity: Decimal | None = None,
    is_floating: bool = False,
    coupon_payments_per_year: int | None = None,
) -> CalculationResult:
    for name, value in (
        ("quantity", quantity),
        ("nominal", nominal),
        ("dirty_quote_percent", dirty_quote_percent),
        ("fx", fx),
    ):
        require_finite(name, value)

    if nominal <= 0:
        raise ValueError("Номинал должен быть положительным")

    if dirty_quote_percent < 0:
        raise ValueError("Котировка не может быть отрицательной")

    if fx <= 0:
        raise ValueError("Валютный курс должен быть положительным")

    if is_floating:
        if (
            type(coupon_payments_per_year) is not int
            or coupon_payments_per_year <= 0
        ):
            raise ValueError(
                "Для floating требуется положительное "
                "целое число купонных выплат в год"
            )

        duration_used = (
            Decimal("1") / Decimal(coupon_payments_per_year)
        )
        convexity_used = Decimal("0")

    else:
        if modified_duration is None or convexity is None:
            raise ValueError(
                "Для расчёта нужны дюрация и выпуклость"
            )

        require_finite("modified_duration", modified_duration)
        require_finite("convexity", convexity)

        duration_used = modified_duration
        convexity_used = convexity

    quote_fraction = dirty_quote_percent / Decimal("100")

    position_value = (
        quantity * nominal * quote_fraction * fx
    )

    result_value = position_value * (
        -duration_used * ONE_BP
        + Decimal("0.5") * convexity_used * ONE_BP ** 2
    )

    require_finite("position_value", position_value)
    require_finite("result_value", result_value)

    return CalculationResult(
        position_value=position_value,
        result_value=result_value,
        duration_used=duration_used,
        convexity_used=convexity_used,
    )
