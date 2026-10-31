from datetime import date
from decimal import Decimal


def is_eligible(
    discount: object,
    subtotal: Decimal,
    quantity: int,
    on_date: date,
) -> bool:
    """
    Pure function to determine if a discount is eligible.
    Covers:
    - active flag
    - date window (inclusive start_date to end_date)
    - usage limit (times_used < usage_limit if usage_limit is not None)
    - minimum purchase (subtotal >= min_purchase if min_purchase is not None)
    - minimum quantity (quantity >= min_quantity if min_quantity is not None)
    """
    is_active = getattr(discount, "is_active", True)
    if not is_active:
        return False

    start_date: date = getattr(discount, "start_date")
    end_date: date = getattr(discount, "end_date")
    if on_date < start_date or on_date > end_date:
        return False

    usage_limit = getattr(discount, "usage_limit", None)
    times_used = getattr(discount, "times_used", 0)
    if usage_limit is not None and times_used >= usage_limit:
        return False

    min_purchase = getattr(discount, "min_purchase", None)
    if min_purchase is not None:
        if not isinstance(min_purchase, Decimal):
            min_purchase = Decimal(str(min_purchase))
        if subtotal < min_purchase:
            return False

    min_quantity = getattr(discount, "min_quantity", None)
    if min_quantity is not None and quantity < min_quantity:
        return False

    return True

