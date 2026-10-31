import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import func, select

from app.api.deps import AdminDep, SessionDep
from app.models import (
    Discount,
    DiscountCreate,
    DiscountProduct,
    DiscountPublic,
    DiscountScope,
    DiscountUpdate,
    Message,
    Page,
    Product,
)
from app.services import audit

router = APIRouter(prefix="/discounts", tags=["discounts"])


def _to_discount_public(discount: Discount, session: SessionDep) -> DiscountPublic:
    link_stmt = select(DiscountProduct.product_id).where(DiscountProduct.discount_id == discount.id)
    product_ids = session.exec(link_stmt).all()
    return DiscountPublic(
        id=discount.id,
        name=discount.name,
        kind=discount.kind,
        value=discount.value,
        scope=discount.scope,
        min_purchase=discount.min_purchase,
        min_quantity=discount.min_quantity,
        start_date=discount.start_date,
        end_date=discount.end_date,
        usage_limit=discount.usage_limit,
        times_used=discount.times_used,
        is_active=discount.is_active,
        created_at=discount.created_at,
        product_ids=list(product_ids),
    )


@router.get("/", response_model=Page[DiscountPublic])
def list_discounts(
    session: SessionDep,
    _: AdminDep,  # ADMIN ONLY
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[DiscountPublic]:
    total = session.exec(select(func.count()).select_from(Discount)).one()
    items = session.exec(
        select(Discount).order_by(Discount.name).offset((page - 1) * limit).limit(limit)
    ).all()
    return Page[DiscountPublic](
        data=[_to_discount_public(d, session) for d in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=DiscountPublic)
def get_discount(
    id: uuid.UUID,
    session: SessionDep,
    _: AdminDep,  # ADMIN ONLY
) -> DiscountPublic:
    discount = session.get(Discount, id)
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    return _to_discount_public(discount, session)


@router.post("/", response_model=DiscountPublic, status_code=status.HTTP_201_CREATED)
def create_discount(
    discount_in: DiscountCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> DiscountPublic:
    if discount_in.scope == DiscountScope.product:
        if not discount_in.product_ids:
            raise HTTPException(
                status_code=400,
                detail="product_ids are required when discount scope is product",
            )
        for pid in discount_in.product_ids:
            product = session.get(Product, pid)
            if not product:
                raise HTTPException(status_code=404, detail=f"Product '{pid}' not found")
    elif discount_in.scope == DiscountScope.subscription:
        if discount_in.product_ids:
            raise HTTPException(
                status_code=400,
                detail="product_ids are forbidden when discount scope is subscription",
            )

    discount = Discount(
        name=discount_in.name,
        kind=discount_in.kind,
        value=discount_in.value,
        scope=discount_in.scope,
        min_purchase=discount_in.min_purchase,
        min_quantity=discount_in.min_quantity,
        start_date=discount_in.start_date,
        end_date=discount_in.end_date,
        usage_limit=discount_in.usage_limit,
        is_active=discount_in.is_active,
        times_used=0,
    )
    session.add(discount)
    session.flush()

    if discount_in.scope == DiscountScope.product:
        for pid in discount_in.product_ids:
            link = DiscountProduct(discount_id=discount.id, product_id=pid)
            session.add(link)

    session.commit()
    session.refresh(discount)

    audit.record(
        session,
        current_user,
        "create",
        "discount",
        discount.id,
        diff=discount_in.model_dump(mode="json"),
    )

    return _to_discount_public(discount, session)


@router.put("/{id}", response_model=DiscountPublic)
def update_discount(
    id: uuid.UUID,
    discount_in: DiscountUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> DiscountPublic:
    discount = session.get(Discount, id)
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")

    new_scope = discount_in.scope if discount_in.scope is not None else discount.scope
    new_product_ids = discount_in.product_ids

    if new_scope == DiscountScope.product:
        existing_links = session.exec(
            select(DiscountProduct.product_id).where(DiscountProduct.discount_id == id)
        ).all()
        pids = new_product_ids if new_product_ids is not None else list(existing_links)
        if not pids:
            raise HTTPException(
                status_code=400,
                detail="product_ids are required when discount scope is product",
            )
        if new_product_ids is not None:
            for pid in new_product_ids:
                if not session.get(Product, pid):
                    raise HTTPException(status_code=404, detail=f"Product '{pid}' not found")
    elif new_scope == DiscountScope.subscription:
        if new_product_ids:
            raise HTTPException(
                status_code=400,
                detail="product_ids are forbidden when discount scope is subscription",
            )

    new_start = discount_in.start_date if discount_in.start_date is not None else discount.start_date
    new_end = discount_in.end_date if discount_in.end_date is not None else discount.end_date
    if new_end < new_start:
        raise HTTPException(status_code=400, detail="end_date must be greater than or equal to start_date")

    new_kind = discount_in.kind if discount_in.kind is not None else discount.kind
    new_val = discount_in.value if discount_in.value is not None else discount.value
    if new_kind == DiscountScope.product or new_kind == "percent":
        if new_val < 0 or new_val > 100:
            raise HTTPException(status_code=400, detail="Percent discount value must be between 0 and 100")
    elif new_kind == "fixed" and new_val <= 0:
        raise HTTPException(status_code=400, detail="Fixed discount value must be strictly positive")

    update_data = discount_in.model_dump(exclude_unset=True, exclude={"product_ids"})
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(discount, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(discount, key, value)

    if new_product_ids is not None:
        # Delete old links
        old_links = session.exec(select(DiscountProduct).where(DiscountProduct.discount_id == id)).all()
        for link in old_links:
            session.delete(link)
        if new_scope == DiscountScope.product:
            for pid in new_product_ids:
                session.add(DiscountProduct(discount_id=id, product_id=pid))
        diff["product_ids"] = [str(pid) for pid in new_product_ids]

    session.add(discount)
    session.commit()
    session.refresh(discount)

    if diff:
        audit.record(session, current_user, "update", "discount", discount.id, diff=diff)

    return _to_discount_public(discount, session)


@router.delete("/{id}", response_model=Message)
def delete_discount(
    id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    discount = session.get(Discount, id)
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")

    audit.record(
        session,
        current_user,
        "delete",
        "discount",
        discount.id,
        diff={"name": discount.name},
    )

    session.delete(discount)
    session.commit()
    return Message(message="Discount deleted successfully")

