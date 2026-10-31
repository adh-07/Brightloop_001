import uuid
from datetime import date
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models import (
    BillingPeriod,
    Discount,
    DiscountKind,
    DiscountProduct,
    DiscountScope,
    PaymentTerm,
    Plan,
    Product,
    ProductType,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    Tax,
    TaxRule,
)


def seed_catalog(session: Session) -> dict[str, int]:
    """
    Seed a believable Brightloop commercial catalog idempotently.
    Running twice results in the exact same record counts.
    """
    # -----------------------------------------------------------------------
    # 1. Taxes & Tax Rules
    # -----------------------------------------------------------------------
    taxes_data = [
        {"name": "GST Standard Rate", "rate": Decimal("18.00"), "is_default": True},
        {"name": "GST Concessional Services", "rate": Decimal("12.00"), "is_default": False},
        {"name": "GST Essential Goods", "rate": Decimal("5.00"), "is_default": False},
    ]
    tax_map: dict[str, Tax] = {}
    for t_data in taxes_data:
        tax = session.exec(select(Tax).where(Tax.name == t_data["name"])).first()
        if not tax:
            tax = Tax(
                name=t_data["name"],
                rate=t_data["rate"],
                is_default=t_data["is_default"],
                is_active=True,
            )
            session.add(tax)
            session.flush()
        tax_map[t_data["name"]] = tax

    # -----------------------------------------------------------------------
    # 2. Payment Terms
    # -----------------------------------------------------------------------
    payment_terms_data = [
        {"name": "Immediate", "due_days": 0, "is_default": True},
        {"name": "Net 15", "due_days": 15, "is_default": False},
        {"name": "Net 30", "due_days": 30, "is_default": False},
    ]
    for pt_data in payment_terms_data:
        pt = session.exec(select(PaymentTerm).where(PaymentTerm.name == pt_data["name"])).first()
        if not pt:
            pt = PaymentTerm(
                name=pt_data["name"],
                due_days=pt_data["due_days"],
                is_default=pt_data["is_default"],
            )
            session.add(pt)
            session.flush()

    # -----------------------------------------------------------------------
    # 3. Products & Variants (8 believable commercial products)
    # -----------------------------------------------------------------------
    products_data = [
        {
            "name": "Brightloop Core ERP Platform",
            "type": ProductType.software,
            "sales_price": Decimal("1200.00"),
            "cost_price": Decimal("300.00"),
            "notes": "Enterprise resource planning core system with finance, supply chain, and reporting modules.",
            "variants": [],
        },
        {
            "name": "Connector Bridge Edition",
            "type": ProductType.software,
            "sales_price": Decimal("800.00"),
            "cost_price": Decimal("200.00"),
            "notes": "Third-party accounting and inventory integration engine.",
            "variants": [
                {"attribute": "Brand", "value": "Odoo", "extra_price": Decimal("560.00")},
                {"attribute": "Brand", "value": "SAP", "extra_price": Decimal("950.00")},
                {"attribute": "Brand", "value": "QuickBooks", "extra_price": Decimal("250.00")},
            ],
        },
        {
            "name": "Point of Sale Terminal Pro",
            "type": ProductType.physical,
            "sales_price": Decimal("650.00"),
            "cost_price": Decimal("420.00"),
            "notes": "Hardened touch-screen POS hardware terminal with integrated NFC reader and receipt printer.",
            "variants": [],
        },
        {
            "name": "Barcode Scanner Wireless Handheld",
            "type": ProductType.physical,
            "sales_price": Decimal("180.00"),
            "cost_price": Decimal("95.00"),
            "notes": "Industrial 2D wireless barcode scanner with Bluetooth base station and cradle.",
            "variants": [],
        },
        {
            "name": "Warehouse Management Extension",
            "type": ProductType.addon,
            "sales_price": Decimal("350.00"),
            "cost_price": Decimal("80.00"),
            "notes": "Advanced bin allocation, multi-facility routing, and pick-pack-ship automation module.",
            "variants": [],
        },
        {
            "name": "Multi-Currency Payroll Pack",
            "type": ProductType.addon,
            "sales_price": Decimal("220.00"),
            "cost_price": Decimal("50.00"),
            "notes": "Automated international payroll calculation with multi-jurisdiction compliance filing.",
            "variants": [],
        },
        {
            "name": "Enterprise Implementation and Onboarding",
            "type": ProductType.service,
            "sales_price": Decimal("2500.00"),
            "cost_price": Decimal("1200.00"),
            "notes": "Comprehensive onboarding including business process mapping, data migration, and administrator training.",
            "variants": [],
        },
        {
            "name": "24/7 Dedicated Technical Support SLA",
            "type": ProductType.service,
            "sales_price": Decimal("900.00"),
            "cost_price": Decimal("400.00"),
            "notes": "Priority queue access with guaranteed 15-minute response time and designated solutions architect.",
            "variants": [],
        },
    ]

    product_map: dict[str, Product] = {}
    variant_map: dict[tuple[str, str, str], ProductVariant] = {}

    for p_data in products_data:
        product = session.exec(select(Product).where(Product.name == p_data["name"])).first()
        if not product:
            product = Product(
                name=p_data["name"],
                type=p_data["type"],
                sales_price=p_data["sales_price"],
                cost_price=p_data["cost_price"],
                notes=p_data["notes"],
                is_active=True,
            )
            session.add(product)
            session.flush()

            for v_data in p_data["variants"]:
                variant = ProductVariant(
                    product_id=product.id,
                    attribute=v_data["attribute"],
                    value=v_data["value"],
                    extra_price=v_data["extra_price"],
                )
                session.add(variant)
                session.flush()
                variant_map[(product.name, v_data["attribute"], v_data["value"])] = variant
        else:
            for v_data in p_data["variants"]:
                variant = session.exec(
                    select(ProductVariant).where(
                        ProductVariant.product_id == product.id,
                        ProductVariant.attribute == v_data["attribute"],
                        ProductVariant.value == v_data["value"],
                    )
                ).first()
                if variant:
                    variant_map[(product.name, v_data["attribute"], v_data["value"])] = variant

        product_map[p_data["name"]] = product

    # -----------------------------------------------------------------------
    # Tax Rules
    # -----------------------------------------------------------------------
    tax_rules_data = [
        {"tax_id": tax_map["GST Concessional Services"].id, "product_type": ProductType.service, "product_id": None, "priority": 10},
        {"tax_id": tax_map["GST Essential Goods"].id, "product_type": ProductType.physical, "product_id": None, "priority": 10},
        {
            "tax_id": tax_map["GST Essential Goods"].id,
            "product_type": None,
            "product_id": product_map["Point of Sale Terminal Pro"].id,
            "priority": 50,
        },
    ]
    for r_data in tax_rules_data:
        existing_rule = session.exec(
            select(TaxRule).where(
                TaxRule.tax_id == r_data["tax_id"],
                TaxRule.product_type == r_data["product_type"],
                TaxRule.product_id == r_data["product_id"],
            )
        ).first()
        if not existing_rule:
            rule = TaxRule(
                tax_id=r_data["tax_id"],
                product_type=r_data["product_type"],
                product_id=r_data["product_id"],
                priority=r_data["priority"],
            )
            session.add(rule)
            session.flush()

    # -----------------------------------------------------------------------
    # 4. Plans (4 plans across monthly/yearly/weekly/daily with different flags)
    # -----------------------------------------------------------------------
    plans_data = [
        {
            "name": "Starter Cloud Monthly",
            "price": Decimal("49.00"),
            "billing_period": BillingPeriod.monthly,
            "min_quantity": 1,
            "available_from": date(2026, 1, 1),
            "available_to": None,
            "auto_close": False,
            "closable": True,
            "pausable": True,
            "renewable": True,
            "is_active": True,
        },
        {
            "name": "Enterprise Annual Retainer",
            "price": Decimal("4990.00"),
            "billing_period": BillingPeriod.yearly,
            "min_quantity": 5,
            "available_from": date(2026, 1, 1),
            "available_to": None,
            "auto_close": False,
            "closable": False,
            "pausable": False,
            "renewable": True,
            "is_active": True,
        },
        {
            "name": "Sprint Support Weekly",
            "price": Decimal("350.00"),
            "billing_period": BillingPeriod.weekly,
            "min_quantity": 1,
            "available_from": date(2026, 3, 1),
            "available_to": date(2026, 12, 31),
            "auto_close": True,
            "closable": True,
            "pausable": True,
            "renewable": False,
            "is_active": True,
        },
        {
            "name": "Emergency Field Operations Daily",
            "price": Decimal("120.00"),
            "billing_period": BillingPeriod.daily,
            "min_quantity": 1,
            "available_from": date(2026, 6, 1),
            "available_to": None,
            "auto_close": True,
            "closable": True,
            "pausable": False,
            "renewable": False,
            "is_active": True,
        },
    ]

    plan_map: dict[str, Plan] = {}
    for pl_data in plans_data:
        plan = session.exec(select(Plan).where(Plan.name == pl_data["name"])).first()
        if not plan:
            plan = Plan(
                name=pl_data["name"],
                price=pl_data["price"],
                billing_period=pl_data["billing_period"],
                min_quantity=pl_data["min_quantity"],
                available_from=pl_data["available_from"],
                available_to=pl_data["available_to"],
                auto_close=pl_data["auto_close"],
                closable=pl_data["closable"],
                pausable=pl_data["pausable"],
                renewable=pl_data["renewable"],
                is_active=pl_data["is_active"],
            )
            session.add(plan)
            session.flush()
        plan_map[pl_data["name"]] = plan

    # -----------------------------------------------------------------------
    # 5. Discounts (4 discounts: 10% sub > 5 seats, fixed 500 off product with limit 20, expired, not-yet-started)
    # -----------------------------------------------------------------------
    discounts_data = [
        {
            "name": "Volume Subscription Discount",
            "kind": DiscountKind.percent,
            "value": Decimal("10.00"),
            "scope": DiscountScope.subscription,
            "min_purchase": None,
            "min_quantity": 5,
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "usage_limit": None,
            "is_active": True,
            "product_names": [],
        },
        {
            "name": "Hardware Launch Rebate",
            "kind": DiscountKind.fixed,
            "value": Decimal("500.00"),
            "scope": DiscountScope.product,
            "min_purchase": Decimal("1000.00"),
            "min_quantity": 1,
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "usage_limit": 20,
            "is_active": True,
            "product_names": ["Point of Sale Terminal Pro"],
        },
        {
            "name": "Quarter One Promotional Concession",
            "kind": DiscountKind.percent,
            "value": Decimal("15.00"),
            "scope": DiscountScope.subscription,
            "min_purchase": None,
            "min_quantity": 1,
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 3, 31),
            "usage_limit": 50,
            "is_active": True,
            "product_names": [],
        },
        {
            "name": "Future Annual Renewal Incentive",
            "kind": DiscountKind.percent,
            "value": Decimal("20.00"),
            "scope": DiscountScope.subscription,
            "min_purchase": Decimal("2000.00"),
            "min_quantity": 1,
            "start_date": date(2026, 11, 15),
            "end_date": date(2026, 12, 31),
            "usage_limit": 100,
            "is_active": True,
            "product_names": [],
        },
    ]

    for d_data in discounts_data:
        discount = session.exec(select(Discount).where(Discount.name == d_data["name"])).first()
        if not discount:
            discount = Discount(
                name=d_data["name"],
                kind=d_data["kind"],
                value=d_data["value"],
                scope=d_data["scope"],
                min_purchase=d_data["min_purchase"],
                min_quantity=d_data["min_quantity"],
                start_date=d_data["start_date"],
                end_date=d_data["end_date"],
                usage_limit=d_data["usage_limit"],
                is_active=d_data["is_active"],
                times_used=0,
            )
            session.add(discount)
            session.flush()

            for p_name in d_data["product_names"]:
                prod = product_map[p_name]
                link = DiscountProduct(discount_id=discount.id, product_id=prod.id)
                session.add(link)
                session.flush()

    # -----------------------------------------------------------------------
    # 6. Quotation Templates (3 quotation templates)
    # -----------------------------------------------------------------------
    quote_templates_data = [
        {
            "name": "Standard Enterprise Onboarding Bundle",
            "validity_days": 30,
            "plan_name": "Starter Cloud Monthly",
            "lines": [
                {"product_name": "Brightloop Core ERP Platform", "variant_key": None, "quantity": 1},
                {"product_name": "Enterprise Implementation and Onboarding", "variant_key": None, "quantity": 1},
                {"product_name": "24/7 Dedicated Technical Support SLA", "variant_key": None, "quantity": 1},
            ],
        },
        {
            "name": "Retail Hardware and POS Station Package",
            "validity_days": 15,
            "plan_name": "Starter Cloud Monthly",
            "lines": [
                {"product_name": "Point of Sale Terminal Pro", "variant_key": None, "quantity": 2},
                {"product_name": "Barcode Scanner Wireless Handheld", "variant_key": None, "quantity": 2},
                {"product_name": "Connector Bridge Edition", "variant_key": ("Connector Bridge Edition", "Brand", "Odoo"), "quantity": 1},
            ],
        },
        {
            "name": "Supply Chain and Warehouse Expansion Pack",
            "validity_days": 45,
            "plan_name": "Enterprise Annual Retainer",
            "lines": [
                {"product_name": "Warehouse Management Extension", "variant_key": None, "quantity": 1},
                {"product_name": "Multi-Currency Payroll Pack", "variant_key": None, "quantity": 1},
                {"product_name": "Enterprise Implementation and Onboarding", "variant_key": None, "quantity": 1},
            ],
        },
    ]

    for qt_data in quote_templates_data:
        template = session.exec(select(QuotationTemplate).where(QuotationTemplate.name == qt_data["name"])).first()
        if not template:
            plan = plan_map.get(qt_data["plan_name"]) if qt_data["plan_name"] else None
            template = QuotationTemplate(
                name=qt_data["name"],
                validity_days=qt_data["validity_days"],
                plan_id=plan.id if plan else None,
                is_active=True,
            )
            session.add(template)
            session.flush()

            for line_data in qt_data["lines"]:
                prod = product_map[line_data["product_name"]]
                variant = variant_map.get(line_data["variant_key"]) if line_data["variant_key"] else None
                line = QuotationTemplateLine(
                    template_id=template.id,
                    product_id=prod.id,
                    variant_id=variant.id if variant else None,
                    quantity=line_data["quantity"],
                )
                session.add(line)
                session.flush()

    session.commit()

    # Return counts for idempotency verification
    counts = {
        "products": session.exec(select(func.count()).select_from(Product)).one(),
        "variants": session.exec(select(func.count()).select_from(ProductVariant)).one(),
        "plans": session.exec(select(func.count()).select_from(Plan)).one(),
        "taxes": session.exec(select(func.count()).select_from(Tax)).one(),
        "tax_rules": session.exec(select(func.count()).select_from(TaxRule)).one(),
        "payment_terms": session.exec(select(func.count()).select_from(PaymentTerm)).one(),
        "discounts": session.exec(select(func.count()).select_from(Discount)).one(),
        "quotation_templates": session.exec(select(func.count()).select_from(QuotationTemplate)).one(),
        "quotation_template_lines": session.exec(select(func.count()).select_from(QuotationTemplateLine)).one(),
    }
    return counts
