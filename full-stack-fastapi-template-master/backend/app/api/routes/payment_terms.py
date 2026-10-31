import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import func, select

from app.api.deps import AdminDep, SessionDep, StaffOrAdminDep
from app.models import (
    Message,
    Page,
    PaymentTerm,
    PaymentTermCreate,
    PaymentTermPublic,
    PaymentTermUpdate,
)
from app.services import audit

router = APIRouter(prefix="/payment-terms", tags=["payment-terms"])


@router.get("/", response_model=Page[PaymentTermPublic])
def list_payment_terms(
    session: SessionDep,
    _: StaffOrAdminDep,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[PaymentTermPublic]:
    total = session.exec(select(func.count()).select_from(PaymentTerm)).one()
    items = session.exec(
        select(PaymentTerm).order_by(PaymentTerm.due_days).offset((page - 1) * limit).limit(limit)
    ).all()
    return Page[PaymentTermPublic](
        data=[PaymentTermPublic.model_validate(p) for p in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=PaymentTermPublic)
def get_payment_term(
    id: uuid.UUID,
    session: SessionDep,
    _: StaffOrAdminDep,
) -> PaymentTermPublic:
    term = session.get(PaymentTerm, id)
    if not term:
        raise HTTPException(status_code=404, detail="Payment term not found")
    return PaymentTermPublic.model_validate(term)


@router.post("/", response_model=PaymentTermPublic, status_code=status.HTTP_201_CREATED)
def create_payment_term(
    term_in: PaymentTermCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> PaymentTermPublic:
    existing_count = session.exec(select(func.count()).select_from(PaymentTerm)).one()

    is_default = term_in.is_default
    if existing_count == 0:
        is_default = True

    if is_default:
        defaults = session.exec(
            select(PaymentTerm).where(PaymentTerm.is_default == True)  # noqa: E712
        ).all()
        for d in defaults:
            d.is_default = False
            session.add(d)

    term = PaymentTerm(
        name=term_in.name,
        due_days=term_in.due_days,
        is_default=is_default,
    )
    session.add(term)
    session.commit()
    session.refresh(term)

    audit.record(
        session,
        current_user,
        "create",
        "payment_term",
        term.id,
        diff=term_in.model_dump(mode="json"),
    )

    return PaymentTermPublic.model_validate(term)


@router.put("/{id}", response_model=PaymentTermPublic)
def update_payment_term(
    id: uuid.UUID,
    term_in: PaymentTermUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> PaymentTermPublic:
    term = session.get(PaymentTerm, id)
    if not term:
        raise HTTPException(status_code=404, detail="Payment term not found")

    if term_in.is_default is False and term.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot unset the default payment term. Set another payment term as default instead.",
        )

    if term_in.is_default is True and not term.is_default:
        defaults = session.exec(
            select(PaymentTerm).where(PaymentTerm.is_default == True, PaymentTerm.id != id)  # noqa: E712
        ).all()
        for d in defaults:
            d.is_default = False
            session.add(d)

    update_data = term_in.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(term, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(term, key, value)

    session.add(term)
    session.commit()
    session.refresh(term)

    if diff:
        audit.record(session, current_user, "update", "payment_term", term.id, diff=diff)

    return PaymentTermPublic.model_validate(term)


@router.delete("/{id}", response_model=Message)
def delete_payment_term(
    id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    term = session.get(PaymentTerm, id)
    if not term:
        raise HTTPException(status_code=404, detail="Payment term not found")

    if term.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default payment term. Designate another payment term as default first.",
        )

    audit.record(
        session,
        current_user,
        "delete",
        "payment_term",
        term.id,
        diff={"name": term.name, "due_days": term.due_days},
    )

    session.delete(term)
    session.commit()
    return Message(message="Payment term deleted successfully")

