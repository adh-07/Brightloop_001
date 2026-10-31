import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import func, select

from app.api.deps import AdminDep, SessionDep, StaffOrAdminDep
from app.models import (
    Message,
    Page,
    Plan,
    Product,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateCreate,
    QuotationTemplateLine,
    QuotationTemplateLinePublic,
    QuotationTemplatePublic,
    QuotationTemplateUpdate,
)
from app.services import audit

router = APIRouter(prefix="/quotation-templates", tags=["quotation-templates"])


def _to_template_public(template: QuotationTemplate) -> QuotationTemplatePublic:
    lines_pub = [
        QuotationTemplateLinePublic(
            id=line.id,
            template_id=line.template_id,
            product_id=line.product_id,
            variant_id=line.variant_id,
            quantity=line.quantity,
        )
        for line in (template.lines or [])
    ]
    return QuotationTemplatePublic(
        id=template.id,
        name=template.name,
        validity_days=template.validity_days,
        plan_id=template.plan_id,
        is_active=template.is_active,
        created_at=template.created_at,
        lines=lines_pub,
    )


def _validate_lines(session: SessionDep, lines: list[Any]) -> None:
    for line in lines:
        product = session.get(Product, line.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{line.product_id}' not found")

        if line.variant_id is not None:
            variant = session.get(ProductVariant, line.variant_id)
            if not variant:
                raise HTTPException(status_code=404, detail=f"Variant '{line.variant_id}' not found")
            if variant.product_id != line.product_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Variant '{line.variant_id}' does not belong to product '{line.product_id}'",
                )


@router.get("/", response_model=Page[QuotationTemplatePublic])
def list_quotation_templates(
    session: SessionDep,
    _: StaffOrAdminDep,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[QuotationTemplatePublic]:
    total = session.exec(select(func.count()).select_from(QuotationTemplate)).one()
    items = session.exec(
        select(QuotationTemplate)
        .order_by(QuotationTemplate.name)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return Page[QuotationTemplatePublic](
        data=[_to_template_public(t) for t in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=QuotationTemplatePublic)
def get_quotation_template(
    id: uuid.UUID,
    session: SessionDep,
    _: StaffOrAdminDep,
) -> QuotationTemplatePublic:
    template = session.get(QuotationTemplate, id)
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")
    return _to_template_public(template)


@router.post("/", response_model=QuotationTemplatePublic, status_code=status.HTTP_201_CREATED)
def create_quotation_template(
    template_in: QuotationTemplateCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> QuotationTemplatePublic:
    if template_in.plan_id is not None:
        plan = session.get(Plan, template_in.plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{template_in.plan_id}' not found")

    _validate_lines(session, template_in.lines)

    template = QuotationTemplate(
        name=template_in.name,
        validity_days=template_in.validity_days,
        plan_id=template_in.plan_id,
        is_active=template_in.is_active,
    )
    session.add(template)
    session.flush()

    for line_in in template_in.lines:
        line = QuotationTemplateLine(
            template_id=template.id,
            product_id=line_in.product_id,
            variant_id=line_in.variant_id,
            quantity=line_in.quantity,
        )
        session.add(line)

    session.commit()
    session.refresh(template)

    audit.record(
        session,
        current_user,
        "create",
        "quotation_template",
        template.id,
        diff=template_in.model_dump(mode="json"),
    )

    return _to_template_public(template)


@router.put("/{id}", response_model=QuotationTemplatePublic)
def update_quotation_template(
    id: uuid.UUID,
    template_in: QuotationTemplateUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> QuotationTemplatePublic:
    template = session.get(QuotationTemplate, id)
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")

    if template_in.plan_id is not None:
        plan = session.get(Plan, template_in.plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{template_in.plan_id}' not found")

    if template_in.lines is not None:
        _validate_lines(session, template_in.lines)

    update_data = template_in.model_dump(exclude_unset=True, exclude={"lines"})
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(template, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(template, key, value)

    if template_in.lines is not None:
        old_lines = session.exec(
            select(QuotationTemplateLine).where(QuotationTemplateLine.template_id == id)
        ).all()
        for old_line in old_lines:
            session.delete(old_line)

        for line_in in template_in.lines:
            new_line = QuotationTemplateLine(
                template_id=template.id,
                product_id=line_in.product_id,
                variant_id=line_in.variant_id,
                quantity=line_in.quantity,
            )
            session.add(new_line)
        diff["lines"] = [line_in.model_dump(mode="json") for line_in in template_in.lines]

    session.add(template)
    session.commit()
    session.refresh(template)

    if diff:
        audit.record(session, current_user, "update", "quotation_template", template.id, diff=diff)

    return _to_template_public(template)


@router.delete("/{id}", response_model=Message)
def delete_quotation_template(
    id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    template = session.get(QuotationTemplate, id)
    if not template:
        raise HTTPException(status_code=404, detail="Quotation template not found")

    audit.record(
        session,
        current_user,
        "delete",
        "quotation_template",
        template.id,
        diff={"name": template.name},
    )

    session.delete(template)
    session.commit()
    return Message(message="Quotation template deleted successfully")

