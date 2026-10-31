from decimal import Decimal
import pytest
from sqlmodel import Session, select

from app.models import Product, ProductType, Tax, TaxRule
from app.services.tax import resolve_tax


def test_tax_resolver_all_branches(db: Session) -> None:
    # Set up default tax (18%)
    default_tax = Tax(name="Standard 18%", rate=Decimal("18.00"), is_default=True, is_active=True)
    concessional_tax = Tax(name="Concessional 12%", rate=Decimal("12.00"), is_default=False, is_active=True)
    essential_tax = Tax(name="Essential 5%", rate=Decimal("5.00"), is_default=False, is_active=True)

    db.add(default_tax)
    db.add(concessional_tax)
    db.add(essential_tax)
    db.commit()
    db.refresh(default_tax)
    db.refresh(concessional_tax)
    db.refresh(essential_tax)

    # Products
    software_prod = Product(name="Cloud Accounting", type=ProductType.software, sales_price=Decimal("100.00"), cost_price=Decimal("20.00"))
    service_prod = Product(name="Consulting Service", type=ProductType.service, sales_price=Decimal("200.00"), cost_price=Decimal("50.00"))
    special_prod = Product(name="Special Hardware", type=ProductType.physical, sales_price=Decimal("500.00"), cost_price=Decimal("300.00"))

    db.add(software_prod)
    db.add(service_prod)
    db.add(special_prod)
    db.commit()
    db.refresh(software_prod)
    db.refresh(service_prod)
    db.refresh(special_prod)

    # 1. Product-type rule for service -> 12%
    type_rule = TaxRule(tax_id=concessional_tax.id, product_type=ProductType.service, product_id=None, priority=10)
    db.add(type_rule)

    # 2. Product-specific rule for special_prod -> 5%
    product_rule = TaxRule(tax_id=essential_tax.id, product_type=None, product_id=special_prod.id, priority=20)
    db.add(product_rule)
    db.commit()

    # Branch 1 test: Product-specific rule takes highest precedence
    resolved_special = resolve_tax(db, special_prod)
    assert resolved_special.id == essential_tax.id
    assert resolved_special.rate == Decimal("5.00")

    # Branch 2 test: Product-type rule takes precedence over default
    resolved_service = resolve_tax(db, service_prod)
    assert resolved_service.id == concessional_tax.id
    assert resolved_service.rate == Decimal("12.00")

    # Branch 3 test: Default tax used when no rule matches
    resolved_software = resolve_tax(db, software_prod)
    assert resolved_software.id == default_tax.id
    assert resolved_software.rate == Decimal("18.00")

    # Branch 4 test: Fallback raises ValueError if no default tax active
    default_tax.is_active = False
    db.add(default_tax)
    db.commit()

    with pytest.raises(ValueError, match="No applicable tax rule or active default tax found"):
        resolve_tax(db, software_prod)

    # Cleanup
    default_tax.is_active = True
    db.add(default_tax)
    db.commit()

