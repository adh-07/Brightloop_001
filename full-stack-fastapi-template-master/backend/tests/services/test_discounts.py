import uuid
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.models import Discount, DiscountCreate, DiscountKind, DiscountScope
from app.services.discounts import is_eligible


def test_discount_model_validation_rules() -> None:
    # Scope product requires product_ids
    with pytest.raises(ValidationError):
        DiscountCreate(
            name="Product Discount Without Products",
            kind=DiscountKind.percent,
            value=Decimal("10.00"),
            scope=DiscountScope.product,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            product_ids=[],  # Forbidden empty for product scope
        )

    # Scope subscription forbids product_ids
    with pytest.raises(ValidationError):
        DiscountCreate(
            name="Subscription Discount With Products",
            kind=DiscountKind.percent,
            value=Decimal("10.00"),
            scope=DiscountScope.subscription,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            product_ids=[uuid.uuid4()],  # Forbidden for subscription scope
        )

    # End date before start date
    with pytest.raises(ValidationError):
        DiscountCreate(
            name="Invalid Dates",
            kind=DiscountKind.percent,
            value=Decimal("10.00"),
            scope=DiscountScope.subscription,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 4, 30),
        )

    # Percent out of range
    with pytest.raises(ValidationError):
        DiscountCreate(
            name="Invalid Percent",
            kind=DiscountKind.percent,
            value=Decimal("105.00"),
            scope=DiscountScope.subscription,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

    # Fixed <= 0
    with pytest.raises(ValidationError):
        DiscountCreate(
            name="Invalid Fixed",
            kind=DiscountKind.fixed,
            value=Decimal("0.00"),
            scope=DiscountScope.subscription,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )


def test_is_eligible_date_window_boundaries() -> None:
    start = date(2026, 3, 1)
    end = date(2026, 3, 31)
    discount = Discount(
        name="Spring Sale",
        kind=DiscountKind.percent,
        value=Decimal("15.00"),
        scope=DiscountScope.subscription,
        start_date=start,
        end_date=end,
        is_active=True,
    )

    # Exact start day -> True
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=start) is True
    # Exact end day -> True
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=end) is True
    # Day before start day -> False
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=date(2026, 2, 28)) is False
    # Day after end day -> False
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=date(2026, 4, 1)) is False


def test_is_eligible_usage_limit_boundaries() -> None:
    discount = Discount(
        name="Limited Coupon",
        kind=DiscountKind.fixed,
        value=Decimal("50.00"),
        scope=DiscountScope.subscription,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        usage_limit=10,
        times_used=9,  # limit - 1
        is_active=True,
    )
    # limit - 1 -> eligible
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=date(2026, 6, 1)) is True

    # limit reached -> ineligible
    discount.times_used = 10
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=date(2026, 6, 1)) is False

    # limit exceeded -> ineligible
    discount.times_used = 11
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=1, on_date=date(2026, 6, 1)) is False


def test_is_eligible_minimum_purchase_boundaries() -> None:
    discount = Discount(
        name="Tiered Threshold",
        kind=DiscountKind.percent,
        value=Decimal("10.00"),
        scope=DiscountScope.subscription,
        min_purchase=Decimal("500.00"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        is_active=True,
    )
    # Exactly equal to min_purchase -> True
    assert is_eligible(discount, subtotal=Decimal("500.00"), quantity=1, on_date=date(2026, 6, 1)) is True
    # Greater than min_purchase -> True
    assert is_eligible(discount, subtotal=Decimal("500.01"), quantity=1, on_date=date(2026, 6, 1)) is True
    # Less than min_purchase -> False
    assert is_eligible(discount, subtotal=Decimal("499.99"), quantity=1, on_date=date(2026, 6, 1)) is False


def test_is_eligible_minimum_quantity_boundaries() -> None:
    discount = Discount(
        name="Bulk Quantity",
        kind=DiscountKind.percent,
        value=Decimal("10.00"),
        scope=DiscountScope.subscription,
        min_quantity=5,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        is_active=True,
    )
    # Exactly equal -> True
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=5, on_date=date(2026, 6, 1)) is True
    # Greater -> True
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=6, on_date=date(2026, 6, 1)) is True
    # Less -> False
    assert is_eligible(discount, subtotal=Decimal("100.00"), quantity=4, on_date=date(2026, 6, 1)) is False


def test_is_eligible_inactive_flag() -> None:
    discount = Discount(
        name="Disabled Promotion",
        kind=DiscountKind.percent,
        value=Decimal("10.00"),
        scope=DiscountScope.subscription,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        is_active=False,
    )
    assert is_eligible(discount, subtotal=Decimal("1000.00"), quantity=10, on_date=date(2026, 6, 1)) is False

