import random
from decimal import Decimal, ROUND_HALF_UP
import pytest

from app.models import Product, ProductType, ProductVariant
from app.services.pricing import LineAmounts, effective_unit_price, line_amounts, quantize


def test_quantize() -> None:
    assert quantize(Decimal("10.004")) == Decimal("10.00")
    assert quantize(Decimal("10.005")) == Decimal("10.01")  # ROUND_HALF_UP
    assert quantize(Decimal("10.006")) == Decimal("10.01")
    assert quantize(Decimal("0.00")) == Decimal("0.00")
    assert quantize(Decimal("-5.125")) == Decimal("-5.13")

    with pytest.raises(TypeError):
        quantize(10.5)  # type: ignore


def test_effective_unit_price() -> None:
    product = Product(
        name="Connector Bridge",
        type=ProductType.software,
        sales_price=Decimal("800.00"),
        cost_price=Decimal("200.00"),
    )
    # Without variant
    assert effective_unit_price(product) == Decimal("800.00")

    # With Odoo variant adding 560
    variant = ProductVariant(
        product_id=product.id,
        attribute="Brand",
        value="Odoo",
        extra_price=Decimal("560.00"),
    )
    assert effective_unit_price(product, variant) == Decimal("1360.00")


def test_line_amounts_basic() -> None:
    amounts = line_amounts(
        unit_price=Decimal("100.00"),
        qty=2,
        discount_amount=Decimal("20.00"),
        tax_rate=Decimal("18.00"),
    )
    assert amounts.gross == Decimal("200.00")
    assert amounts.discount == Decimal("20.00")
    assert amounts.taxable == Decimal("180.00")
    assert amounts.tax == Decimal("32.40")  # 180 * 0.18 = 32.40
    assert amounts.total == Decimal("212.40")  # 180 + 32.40 = 212.40
    assert amounts.total == amounts.taxable + amounts.tax


def test_line_amounts_discount_exceeds_gross() -> None:
    amounts = line_amounts(
        unit_price=Decimal("50.00"),
        qty=1,
        discount_amount=Decimal("80.00"),
        tax_rate=Decimal("10.00"),
    )
    assert amounts.gross == Decimal("50.00")
    assert amounts.discount == Decimal("50.00")
    assert amounts.taxable == Decimal("0.00")
    assert amounts.tax == Decimal("0.00")
    assert amounts.total == Decimal("0.00")


def test_line_amounts_type_checks() -> None:
    with pytest.raises(TypeError):
        line_amounts(unit_price=10.0, qty=1)  # type: ignore
    with pytest.raises(TypeError):
        line_amounts(unit_price=Decimal("10.00"), qty="two")  # type: ignore
    with pytest.raises(TypeError):
        line_amounts(unit_price=Decimal("10.00"), qty=1, discount_amount=1.5)  # type: ignore
    with pytest.raises(TypeError):
        line_amounts(unit_price=Decimal("10.00"), qty=1, tax_rate=18.0)  # type: ignore


def test_pricing_property_tests_random_decimals() -> None:
    """Property-style test with 100 random Decimals verifying total == taxable + tax."""
    for _ in range(100):
        cents_price = random.randint(1, 100000)
        cents_qty = random.randint(1, 20)
        cents_disc = random.randint(0, 10000)
        cents_tax = random.randint(0, 3000)

        price = Decimal(cents_price) / Decimal("100")
        qty = Decimal(cents_qty)
        disc = Decimal(cents_disc) / Decimal("100")
        tax_rate = Decimal(cents_tax) / Decimal("100")

        amounts = line_amounts(price, qty, disc, tax_rate)

        # Invariant 1: total must exactly equal taxable + tax
        assert amounts.total == amounts.taxable + amounts.tax
        # Invariant 2: gross must equal quantize(price * qty)
        assert amounts.gross == (price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Invariant 3: taxable must equal max(0, gross - discount)
        expected_taxable = max(Decimal("0.00"), amounts.gross - amounts.discount)
        assert amounts.taxable == expected_taxable


def test_pricing_property_multiple_lines_sum() -> None:
    """Verify that multiple line totals match the sum of individual rounded lines."""
    lines: list[LineAmounts] = []
    for _ in range(5):
        price = Decimal(random.randint(100, 5000)) / Decimal("100")
        qty = random.randint(1, 10)
        disc = Decimal(random.randint(0, 500)) / Decimal("100")
        tax_rate = Decimal("18.00")
        lines.append(line_amounts(price, qty, disc, tax_rate))

    total_gross = sum((l.gross for l in lines), Decimal("0.00"))
    total_taxable = sum((l.taxable for l in lines), Decimal("0.00"))
    total_tax = sum((l.tax for l in lines), Decimal("0.00"))
    total_amount = sum((l.total for l in lines), Decimal("0.00"))

    assert total_amount == total_taxable + total_tax

