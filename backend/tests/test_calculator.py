from decimal import Decimal

import pytest

from app.calculator import calculate_dv01


def test_fixed_coupon():
    result = calculate_dv01(
        quantity=Decimal("100"),
        nominal=Decimal("1000"),
        dirty_quote_percent=Decimal("95"),
        fx=Decimal("1"),
        modified_duration=Decimal("4"),
        convexity=Decimal("20"),
    )

    assert result.position_value == Decimal("95000")
    assert result.result_value == Decimal("-37.9905")


def test_short_position():
    result = calculate_dv01(
        quantity=Decimal("-100"),
        nominal=Decimal("1000"),
        dirty_quote_percent=Decimal("95"),
        fx=Decimal("1"),
        modified_duration=Decimal("4"),
        convexity=Decimal("20"),
    )

    assert result.position_value == Decimal("-95000")
    assert result.result_value == Decimal("37.9905")


def test_floating_coupon():
    result = calculate_dv01(
        quantity=Decimal("100"),
        nominal=Decimal("1000"),
        dirty_quote_percent=Decimal("95"),
        fx=Decimal("1"),
        is_floating=True,
        coupon_payments_per_year=4,
    )

    assert result.duration_used == Decimal("0.25")
    assert result.convexity_used == Decimal("0")
    assert result.result_value == Decimal("-2.375")


def test_invalid_coupon_frequency():
    with pytest.raises(ValueError):
        calculate_dv01(
            quantity=Decimal("100"),
            nominal=Decimal("1000"),
            dirty_quote_percent=Decimal("95"),
            fx=Decimal("1"),
            is_floating=True,
            coupon_payments_per_year=0,
        )