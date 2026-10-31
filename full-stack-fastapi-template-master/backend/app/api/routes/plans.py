import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import func, select

from app.api.deps import AdminDep, SessionDep, StaffOrAdminDep
from app.models import Message, Page, Plan, PlanCreate, PlanPublic, PlanUpdate
from app.services import audit
from app.services.clock import get_clock

router = APIRouter(prefix="/plans", tags=["plans"])


def _to_plan_public(plan: Plan) -> PlanPublic:
    clock = get_clock()
    today = clock.today()
    is_available = (
        plan.is_active
        and (plan.available_from <= today)
        and (plan.available_to is None or plan.available_to >= today)
    )
    return PlanPublic(
        id=plan.id,
        name=plan.name,
        price=plan.price,
        billing_period=plan.billing_period,
        min_quantity=plan.min_quantity,
        available_from=plan.available_from,
        available_to=plan.available_to,
        auto_close=plan.auto_close,
        closable=plan.closable,
        pausable=plan.pausable,
        renewable=plan.renewable,
        is_active=plan.is_active,
        created_at=plan.created_at,
        is_available_today=is_available,
    )


@router.get("/", response_model=Page[PlanPublic])
def list_plans(
    session: SessionDep,
    _: StaffOrAdminDep,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[PlanPublic]:
    total = session.exec(select(func.count()).select_from(Plan)).one()
    items = session.exec(
        select(Plan).order_by(Plan.name).offset((page - 1) * limit).limit(limit)
    ).all()
    return Page[PlanPublic](
        data=[_to_plan_public(p) for p in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=PlanPublic)
def get_plan(
    id: uuid.UUID,
    session: SessionDep,
    _: StaffOrAdminDep,
) -> PlanPublic:
    plan = session.get(Plan, id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _to_plan_public(plan)


@router.post("/", response_model=PlanPublic, status_code=status.HTTP_201_CREATED)
def create_plan(
    plan_in: PlanCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> PlanPublic:
    plan = Plan.model_validate(plan_in)
    session.add(plan)
    session.commit()
    session.refresh(plan)

    audit.record(
        session,
        current_user,
        "create",
        "plan",
        plan.id,
        diff=plan_in.model_dump(mode="json"),
    )

    return _to_plan_public(plan)


@router.put("/{id}", response_model=PlanPublic)
def update_plan(
    id: uuid.UUID,
    plan_in: PlanUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> PlanPublic:
    plan = session.get(Plan, id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    new_from = plan_in.available_from if plan_in.available_from is not None else plan.available_from
    new_to = plan_in.available_to if plan_in.available_to is not None else plan.available_to
    if new_to is not None and new_to < new_from:
        raise HTTPException(
            status_code=400,
            detail="available_to must be greater than or equal to available_from",
        )

    update_data = plan_in.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(plan, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(plan, key, value)

    session.add(plan)
    session.commit()
    session.refresh(plan)

    if diff:
        audit.record(session, current_user, "update", "plan", plan.id, diff=diff)

    return _to_plan_public(plan)


@router.delete("/{id}", response_model=Message)
def delete_plan(
    id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    plan = session.get(Plan, id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    audit.record(
        session,
        current_user,
        "delete",
        "plan",
        plan.id,
        diff={"name": plan.name},
    )

    session.delete(plan)
    session.commit()
    return Message(message="Plan deleted successfully")

