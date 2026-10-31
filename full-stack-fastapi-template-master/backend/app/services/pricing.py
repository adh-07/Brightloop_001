from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

TWO_PLACES = Decimal("0.01")


def quantize(amount: Decimal) -> Decimal:
    """Quantize a Decimal to 2 decimal places using ROUND_HALF_UP."""
    if not isinstance(amount, Decimal):
        raise TypeError(f"Expected Decimal, got {type(amount).__name__}")
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class LineAmounts(NamedTuple):
    gross: Decimal
    discount: Decimal
    taxable: Decimal
    tax: Decimal
    total: Decimal


def effective_unit_price(product: object, variant: object | None = None) -> Decimal:
    """Calculate effective unit price: product sales_price + variant extra_price."""
    sales_price = getattr(product, "sales_price", Decimal("0.00"))
    if not isinstance(sales_price, Decimal):
        sales_price = Decimal(str(sales_price))

    extra_price = Decimal("0.00")
    if variant is not None:
        extra = getattr(variant, "extra_price", Decimal("0.00"))
        extra_price = extra if isinstance(extra, Decimal) else Decimal(str(extra))

    return quantize(sales_price + extra_price)


def line_amounts(
    unit_price: Decimal,
    qty: int | Decimal,
    discount_amount: Decimal = Decimal("0.00"),
    tax_rate: Decimal = Decimal("0.00"),
) -> LineAmounts:
    """
    Calculate line amounts with 2 decimal place rounding:
    gross = quantize(unit_price * qty)
    discount = quantize(discount_amount)
    taxable = max(0, gross - discount)
    tax = quantize(taxable * (tax_rate / 100))
    total = taxable + tax
    """
    if not isinstance(unit_price, Decimal):
        raise TypeError(f"unit_price must be Decimal, got {type(unit_price).__name__}")
    if not isinstance(qty, (int, Decimal)):
        raise TypeError(f"qty must be int or Decimal, got {type(qty).__name__}")
    if not isinstance(discount_amount, Decimal):
        raise TypeError(f"discount_amount must be Decimal, got {type(discount_amount).__name__}")
    if not isinstance(tax_rate, Decimal):
        raise TypeError(f"tax_rate must be Decimal, got {type(tax_rate).__name__}")

    dec_qty = Decimal(qty) if isinstance(qty, int) else qty

    gross = quantize(unit_price * dec_qty)
    discount = quantize(discount_amount)
    # discount cannot exceed gross for taxable computation
    if discount > gross:
        discount = gross
    taxable = quantize(gross - discount)

    # tax = quantize(taxable * (tax_rate / 100))
    hundred = Decimal("100.00")
    raw_tax = taxable * tax_rate / hundred
    tax = quantize(raw_tax)

    total = quantize(taxable + tax)

    return LineAmounts(
        gross=gross,
        discount=discount,
        taxable=taxable,
        tax=tax,
        total=total,
    )

