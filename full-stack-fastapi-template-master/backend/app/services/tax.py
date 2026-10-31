from sqlmodel import Session, select

from app.models import Product, Tax, TaxRule


def resolve_tax(session: Session, product: Product) -> Tax:
    """
    Resolve applicable tax for a given product with precedence:
    1. Product rule (product_id == product.id)
    2. Product-type rule (product_type == product.type and product_id is None)
    3. Default tax (Tax.is_default is True and is_active is True)
    4. Fallback: raises ValueError if no tax can be resolved
    """
    # 1. Product-specific rule
    if product.id is not None:
        rule_stmt = (
            select(TaxRule)
            .join(Tax)
            .where(
                TaxRule.product_id == product.id,
                Tax.is_active == True,  # noqa: E712
            )
            .order_by(TaxRule.priority.desc())
        )
        product_rule = session.exec(rule_stmt).first()
        if product_rule:
            tax = session.get(Tax, product_rule.tax_id)
            if tax and tax.is_active:
                return tax

    # 2. Product-type rule
    if product.type is not None:
        rule_stmt = (
            select(TaxRule)
            .join(Tax)
            .where(
                TaxRule.product_type == product.type,
                TaxRule.product_id.is_(None),
                Tax.is_active == True,  # noqa: E712
            )
            .order_by(TaxRule.priority.desc())
        )
        type_rule = session.exec(rule_stmt).first()
        if type_rule:
            tax = session.get(Tax, type_rule.tax_id)
            if tax and tax.is_active:
                return tax

    # 3. Default tax
    default_tax_stmt = (
        select(Tax)
        .where(
            Tax.is_default == True,  # noqa: E712
            Tax.is_active == True,  # noqa: E712
        )
    )
    default_tax = session.exec(default_tax_stmt).first()
    if default_tax:
        return default_tax

    # 4. Fallback
    raise ValueError(f"No applicable tax rule or active default tax found for product '{product.name}'")

