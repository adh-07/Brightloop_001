import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import func, select

from app.api.deps import AdminDep, SessionDep, StaffOrAdminDep
from app.models import (
    Message,
    Page,
    Product,
    Tax,
    TaxCreate,
    TaxPublic,
    TaxRule,
    TaxRuleCreate,
    TaxRulePublic,
    TaxRuleUpdate,
    TaxUpdate,
)
from app.services import audit

router = APIRouter(prefix="/taxes", tags=["taxes"])


# ---------------------------------------------------------------------------
# Taxes
# ---------------------------------------------------------------------------
@router.get("/", response_model=Page[TaxPublic])
def list_taxes(
    session: SessionDep,
    _: StaffOrAdminDep,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[TaxPublic]:
    total = session.exec(select(func.count()).select_from(Tax)).one()
    items = session.exec(
        select(Tax).order_by(Tax.rate).offset((page - 1) * limit).limit(limit)
    ).all()
    return Page[TaxPublic](
        data=[TaxPublic.model_validate(t) for t in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/rules", response_model=Page[TaxRulePublic])
def list_tax_rules(
    session: SessionDep,
    _: StaffOrAdminDep,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[TaxRulePublic]:
    total = session.exec(select(func.count()).select_from(TaxRule)).one()
    items = session.exec(
        select(TaxRule).order_by(TaxRule.priority.desc()).offset((page - 1) * limit).limit(limit)
    ).all()
    return Page[TaxRulePublic](
        data=[TaxRulePublic.model_validate(r) for r in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=TaxPublic)
def get_tax(
    id: uuid.UUID,
    session: SessionDep,
    _: StaffOrAdminDep,
) -> TaxPublic:
    tax = session.get(Tax, id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")
    return TaxPublic.model_validate(tax)


@router.post("/", response_model=TaxPublic, status_code=status.HTTP_201_CREATED)
def create_tax(
    tax_in: TaxCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> TaxPublic:
    # Transactionally handle default tax constraint
    existing_count = session.exec(select(func.count()).select_from(Tax)).one()

    # If first tax, force is_default to True so exactly one exists
    is_default = tax_in.is_default
    if existing_count == 0:
        is_default = True

    if is_default:
        defaults = session.exec(select(Tax).where(Tax.is_default == True)).all()  # noqa: E712
        for d in defaults:
            d.is_default = False
            session.add(d)

    tax = Tax(
        name=tax_in.name,
        rate=tax_in.rate,
        is_default=is_default,
        is_active=tax_in.is_active,
    )
    session.add(tax)
    session.commit()
    session.refresh(tax)

    audit.record(
        session,
        current_user,
        "create",
        "tax",
        tax.id,
        diff=tax_in.model_dump(mode="json"),
    )

    return TaxPublic.model_validate(tax)


@router.put("/{id}", response_model=TaxPublic)
def update_tax(
    id: uuid.UUID,
    tax_in: TaxUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> TaxPublic:
    tax = session.get(Tax, id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")

    if tax_in.is_default is False and tax.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot unset the default tax. Set another tax as default instead.",
        )

    if tax_in.is_default is True and not tax.is_default:
        defaults = session.exec(
            select(Tax).where(Tax.is_default == True, Tax.id != id)  # noqa: E712
        ).all()
        for d in defaults:
            d.is_default = False
            session.add(d)

    update_data = tax_in.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(tax, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(tax, key, value)

    session.add(tax)
    session.commit()
    session.refresh(tax)

    if diff:
        audit.record(session, current_user, "update", "tax", tax.id, diff=diff)

    return TaxPublic.model_validate(tax)


@router.delete("/{id}", response_model=Message)
def delete_tax(
    id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    tax = session.get(Tax, id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")

    if tax.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default tax. Designate another tax as default first.",
        )

    audit.record(
        session,
        current_user,
        "delete",
        "tax",
        tax.id,
        diff={"name": tax.name, "rate": str(tax.rate)},
    )

    session.delete(tax)
    session.commit()
    return Message(message="Tax deleted successfully")


# ---------------------------------------------------------------------------
# Tax Rules
# ---------------------------------------------------------------------------
@router.post("/rules", response_model=TaxRulePublic, status_code=status.HTTP_201_CREATED)
def create_tax_rule(
    rule_in: TaxRuleCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> TaxRulePublic:
    tax = session.get(Tax, rule_in.tax_id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")

    if rule_in.product_id is not None:
        product = session.get(Product, rule_in.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

    rule = TaxRule.model_validate(rule_in)
    session.add(rule)
    session.commit()
    session.refresh(rule)

    audit.record(
        session,
        current_user,
        "create",
        "tax_rule",
        rule.id,
        diff=rule_in.model_dump(mode="json"),
    )

    return TaxRulePublic.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=TaxRulePublic)
def update_tax_rule(
    rule_id: uuid.UUID,
    rule_in: TaxRuleUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> TaxRulePublic:
    rule = session.get(TaxRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Tax rule not found")

    if rule_in.tax_id is not None:
        tax = session.get(Tax, rule_in.tax_id)
        if not tax:
            raise HTTPException(status_code=404, detail="Tax not found")

    if rule_in.product_id is not None:
        product = session.get(Product, rule_in.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

    target_type = rule_in.product_type if rule_in.product_type is not None else rule.product_type
    target_product = rule_in.product_id if rule_in.product_id is not None else rule.product_id
    if target_type is None and target_product is None:
        raise HTTPException(status_code=400, detail="At least one of product_type or product_id must be set")

    update_data = rule_in.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(rule, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(rule, key, value)

    session.add(rule)
    session.commit()
    session.refresh(rule)

    if diff:
        audit.record(session, current_user, "update", "tax_rule", rule.id, diff=diff)

    return TaxRulePublic.model_validate(rule)


@router.delete("/rules/{rule_id}", response_model=Message)
def delete_tax_rule(
    rule_id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    rule = session.get(TaxRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Tax rule not found")

    audit.record(
        session,
        current_user,
        "delete",
        "tax_rule",
        rule.id,
        diff={"tax_id": str(rule.tax_id), "priority": rule.priority},
    )

    session.delete(rule)
    session.commit()
    return Message(message="Tax rule deleted successfully")

