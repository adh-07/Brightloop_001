import uuid
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import col, func, select

from app.api.deps import AdminDep, SessionDep, StaffOrAdminDep
from app.models import (
    Message,
    Page,
    Product,
    ProductCreate,
    ProductPublic,
    ProductType,
    ProductUpdate,
    ProductVariant,
    ProductVariantCreate,
    ProductVariantPublic,
    ProductVariantUpdate,
)
from app.services import audit
from app.services.pricing import effective_unit_price

router = APIRouter(prefix="/products", tags=["products"])


def _to_variant_public(variant: ProductVariant, product: Product) -> ProductVariantPublic:
    eff_price = effective_unit_price(product, variant)
    return ProductVariantPublic(
        id=variant.id,
        product_id=variant.product_id,
        attribute=variant.attribute,
        value=variant.value,
        extra_price=variant.extra_price,
        effective_price=eff_price,
    )


def _to_product_public(product: Product) -> ProductPublic:
    variants_public = [_to_variant_public(v, product) for v in (product.variants or [])]
    return ProductPublic(
        id=product.id,
        name=product.name,
        type=product.type,
        sales_price=product.sales_price,
        cost_price=product.cost_price,
        notes=product.notes,
        is_active=product.is_active,
        created_at=product.created_at,
        variants=variants_public,
    )


@router.get("/", response_model=Page[ProductPublic])
def list_products(
    session: SessionDep,
    _: StaffOrAdminDep,
    search: str | None = Query(None, description="Search by product name"),
    type: ProductType | None = Query(None, description="Filter by product type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Page[ProductPublic]:
    query = select(Product)
    count_query = select(func.count()).select_from(Product)

    if search:
        query = query.where(col(Product.name).ilike(f"%{search}%"))
        count_query = count_query.where(col(Product.name).ilike(f"%{search}%"))

    if type is not None:
        query = query.where(Product.type == type)
        count_query = count_query.where(Product.type == type)

    if is_active is not None:
        query = query.where(Product.is_active == is_active)
        count_query = count_query.where(Product.is_active == is_active)

    total = session.exec(count_query).one()
    items = session.exec(
        query.order_by(Product.name).offset((page - 1) * limit).limit(limit)
    ).all()

    return Page[ProductPublic](
        data=[_to_product_public(p) for p in items],
        count=total,
        page=page,
        limit=limit,
    )


@router.get("/{id}", response_model=ProductPublic)
def get_product(
    id: uuid.UUID,
    session: SessionDep,
    _: StaffOrAdminDep,
) -> ProductPublic:
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _to_product_public(product)


@router.post("/", response_model=ProductPublic, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> ProductPublic:
    # Check name unique among active products
    if product_in.is_active:
        existing = session.exec(
            select(Product).where(
                Product.name == product_in.name,
                Product.is_active == True,  # noqa: E712
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"An active product with name '{product_in.name}' already exists",
            )

    # Check for duplicate variants within the payload
    seen_variants: set[tuple[str, str]] = set()
    for v in product_in.variants:
        key = (v.attribute.strip().lower(), v.value.strip().lower())
        if key in seen_variants:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate variant ({v.attribute}, {v.value}) in request",
            )
        seen_variants.add(key)

    product = Product(
        name=product_in.name,
        type=product_in.type,
        sales_price=product_in.sales_price,
        cost_price=product_in.cost_price,
        notes=product_in.notes,
        is_active=product_in.is_active,
    )
    session.add(product)
    session.flush()

    for v_in in product_in.variants:
        variant = ProductVariant(
            product_id=product.id,
            attribute=v_in.attribute,
            value=v_in.value,
            extra_price=v_in.extra_price,
        )
        session.add(variant)

    session.commit()
    session.refresh(product)

    audit.record(
        session,
        current_user,
        "create",
        "product",
        product.id,
        diff=product_in.model_dump(mode="json"),
    )

    return _to_product_public(product)


@router.put("/{id}", response_model=ProductPublic)
def update_product(
    id: uuid.UUID,
    product_in: ProductUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> ProductPublic:
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    new_name = product_in.name if product_in.name is not None else product.name
    new_active = product_in.is_active if product_in.is_active is not None else product.is_active

    if new_active:
        existing = session.exec(
            select(Product).where(
                Product.name == new_name,
                Product.is_active == True,  # noqa: E712
                Product.id != product.id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"An active product with name '{new_name}' already exists",
            )

    update_data = product_in.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(product, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(product, key, value)

    session.add(product)
    session.commit()
    session.refresh(product)

    if diff:
        audit.record(session, current_user, "update", "product", product.id, diff=diff)

    return _to_product_public(product)


@router.delete("/{id}", response_model=Message)
def delete_product(
    id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    audit.record(
        session,
        current_user,
        "delete",
        "product",
        product.id,
        diff={"name": product.name, "type": product.type.value},
    )

    session.delete(product)
    session.commit()
    return Message(message="Product deleted successfully")


# ---------------------------------------------------------------------------
# Nested Variant Endpoints
# ---------------------------------------------------------------------------
@router.post("/{product_id}/variants", response_model=ProductVariantPublic, status_code=status.HTTP_201_CREATED)
def add_product_variant(
    product_id: uuid.UUID,
    variant_in: ProductVariantCreate,
    session: SessionDep,
    current_user: AdminDep,
) -> ProductVariantPublic:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = session.exec(
        select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.attribute == variant_in.attribute,
            ProductVariant.value == variant_in.value,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Variant ({variant_in.attribute}, {variant_in.value}) already exists for this product",
        )

    variant = ProductVariant(
        product_id=product_id,
        attribute=variant_in.attribute,
        value=variant_in.value,
        extra_price=variant_in.extra_price,
    )
    session.add(variant)
    session.commit()
    session.refresh(variant)

    audit.record(
        session,
        current_user,
        "create",
        "product_variant",
        variant.id,
        diff=variant_in.model_dump(mode="json"),
    )

    return _to_variant_public(variant, product)


@router.put("/{product_id}/variants/{variant_id}", response_model=ProductVariantPublic)
def update_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    variant_in: ProductVariantUpdate,
    session: SessionDep,
    current_user: AdminDep,
) -> ProductVariantPublic:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant = session.get(ProductVariant, variant_id)
    if not variant or variant.product_id != product_id:
        raise HTTPException(status_code=404, detail="Variant not found for this product")

    new_attr = variant_in.attribute if variant_in.attribute is not None else variant.attribute
    new_val = variant_in.value if variant_in.value is not None else variant.value

    existing = session.exec(
        select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.attribute == new_attr,
            ProductVariant.value == new_val,
            ProductVariant.id != variant_id,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Variant ({new_attr}, {new_val}) already exists for this product",
        )

    update_data = variant_in.model_dump(exclude_unset=True)
    diff: dict[str, Any] = {}
    for key, value in update_data.items():
        old_val = getattr(variant, key)
        if old_val != value:
            diff[key] = {"old": str(old_val), "new": str(value)}
            setattr(variant, key, value)

    session.add(variant)
    session.commit()
    session.refresh(variant)

    if diff:
        audit.record(session, current_user, "update", "product_variant", variant.id, diff=diff)

    return _to_variant_public(variant, product)


@router.delete("/{product_id}/variants/{variant_id}", response_model=Message)
def delete_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    session: SessionDep,
    current_user: AdminDep,
) -> Message:
    variant = session.get(ProductVariant, variant_id)
    if not variant or variant.product_id != product_id:
        raise HTTPException(status_code=404, detail="Variant not found for this product")

    audit.record(
        session,
        current_user,
        "delete",
        "product_variant",
        variant.id,
        diff={"attribute": variant.attribute, "value": variant.value},
    )

    session.delete(variant)
    session.commit()
    return Message(message="Variant deleted successfully")

