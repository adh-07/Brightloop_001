import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, Optional, Self, TypeVar

from pydantic import EmailStr, field_validator, model_validator
from sqlalchemy import JSON, CheckConstraint, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.services.clock import get_clock


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Generic Pagination
# ---------------------------------------------------------------------------
T = TypeVar("T")


class Page(SQLModel, Generic[T]):
    data: list[T]
    count: int
    page: int = 1
    limit: int = 50

    @property
    def items(self) -> list[T]:
        return self.data

    @property
    def total(self) -> int:
        return self.count


# ---------------------------------------------------------------------------
# Roles & User
# ---------------------------------------------------------------------------
class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    customer = "customer"


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    role: str = Field(default=UserRole.customer.value, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role: str | None = Field(default=None, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    action: str = Field(max_length=50)
    entity_type: str = Field(max_length=50)
    entity_id: str = Field(max_length=255)
    diff: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default={}))
    created_at: datetime = Field(default_factory=get_datetime_utc)


# ---------------------------------------------------------------------------
# Catalog: Product & ProductVariant
# ---------------------------------------------------------------------------
class ProductType(str, Enum):
    software = "software"
    addon = "addon"
    service = "service"
    physical = "physical"


class ProductVariantBase(SQLModel):
    attribute: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=100)
    extra_price: Decimal = Field(default=Decimal("0.00"), decimal_places=2, max_digits=12)

    @field_validator("extra_price", mode="before")
    @classmethod
    def _validate_extra_price(cls, v: Any) -> Decimal:
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("extra_price must be greater than or equal to 0")
        return dec


class ProductVariant(ProductVariantBase, table=True):
    __tablename__ = "product_variant"
    __table_args__ = (
        UniqueConstraint("product_id", "attribute", "value", name="uq_product_variant_attr_val"),
        CheckConstraint("extra_price >= 0", name="ck_product_variant_extra_price_ge_zero"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_id: uuid.UUID = Field(foreign_key="product.id", nullable=False, ondelete="CASCADE")
    product: Optional["Product"] = Relationship(back_populates="variants")


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(SQLModel):
    attribute: str | None = Field(default=None, min_length=1, max_length=100)
    value: str | None = Field(default=None, min_length=1, max_length=100)
    extra_price: Decimal | None = None

    @field_validator("extra_price", mode="before")
    @classmethod
    def _validate_extra_price(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("extra_price must be greater than or equal to 0")
        return dec


class ProductVariantPublic(ProductVariantBase):
    id: uuid.UUID
    product_id: uuid.UUID
    effective_price: Decimal | None = None


class ProductBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    type: ProductType
    sales_price: Decimal = Field(default=Decimal("0.00"), decimal_places=2, max_digits=12)
    cost_price: Decimal = Field(default=Decimal("0.00"), decimal_places=2, max_digits=12)
    notes: str | None = Field(default=None)
    is_active: bool = Field(default=True)

    @field_validator("sales_price", "cost_price", mode="before")
    @classmethod
    def _validate_prices(cls, v: Any) -> Decimal:
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("Prices must be greater than or equal to 0")
        return dec


class Product(ProductBase, table=True):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint("sales_price >= 0", name="ck_product_sales_price_ge_zero"),
        CheckConstraint("cost_price >= 0", name="ck_product_cost_price_ge_zero"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    variants: list[ProductVariant] = Relationship(back_populates="product", cascade_delete=True)


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = Field(default_factory=list)


class ProductUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: ProductType | None = None
    sales_price: Decimal | None = None
    cost_price: Decimal | None = None
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("sales_price", "cost_price", mode="before")
    @classmethod
    def _validate_optional_prices(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("Prices must be greater than or equal to 0")
        return dec


class ProductPublic(ProductBase):
    id: uuid.UUID
    created_at: datetime
    variants: list[ProductVariantPublic] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
class BillingPeriod(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class PlanBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(default=Decimal("0.00"), decimal_places=2, max_digits=12)
    billing_period: BillingPeriod
    min_quantity: int = Field(default=1, ge=1)
    available_from: date
    available_to: date | None = Field(default=None)
    auto_close: bool = Field(default=False)
    closable: bool = Field(default=True)
    pausable: bool = Field(default=True)
    renewable: bool = Field(default=True)
    is_active: bool = Field(default=True)

    @field_validator("price", mode="before")
    @classmethod
    def _validate_price(cls, v: Any) -> Decimal:
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("Price must be greater than or equal to 0")
        return dec

    @field_validator("min_quantity", mode="before")
    @classmethod
    def _validate_min_quantity(cls, v: Any) -> int:
        val = int(v)
        if val < 1:
            raise ValueError("min_quantity must be at least 1")
        return val

    @model_validator(mode="after")
    def _validate_dates(self) -> Self:
        if self.available_to is not None and self.available_to < self.available_from:
            raise ValueError("available_to must be greater than or equal to available_from")
        return self


class Plan(PlanBase, table=True):
    __tablename__ = "plan"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_plan_price_ge_zero"),
        CheckConstraint("min_quantity >= 1", name="ck_plan_min_quantity_ge_one"),
        CheckConstraint(
            "available_to IS NULL OR available_to >= available_from",
            name="ck_plan_available_to_ge_from",
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PlanCreate(PlanBase):
    pass


class PlanUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = None
    billing_period: BillingPeriod | None = None
    min_quantity: int | None = None
    available_from: date | None = None
    available_to: date | None = None
    auto_close: bool | None = None
    closable: bool | None = None
    pausable: bool | None = None
    renewable: bool | None = None
    is_active: bool | None = None

    @field_validator("price", mode="before")
    @classmethod
    def _validate_optional_price(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("Price must be greater than or equal to 0")
        return dec

    @field_validator("min_quantity", mode="before")
    @classmethod
    def _validate_optional_min_quantity(cls, v: Any) -> int | None:
        if v is None:
            return None
        val = int(v)
        if val < 1:
            raise ValueError("min_quantity must be at least 1")
        return val


class PlanPublic(PlanBase):
    id: uuid.UUID
    created_at: datetime
    is_available_today: bool = False


# ---------------------------------------------------------------------------
# Taxes and Tax Rules
# ---------------------------------------------------------------------------
class TaxBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    rate: Decimal = Field(decimal_places=2, max_digits=5)
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)

    @field_validator("rate", mode="before")
    @classmethod
    def _validate_rate(cls, v: Any) -> Decimal:
        dec = Decimal(str(v))
        if dec < Decimal("0.00") or dec > Decimal("100.00"):
            raise ValueError("Tax rate must be between 0 and 100")
        return dec


class Tax(TaxBase, table=True):
    __tablename__ = "tax"
    __table_args__ = (
        CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_rate_range"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class TaxCreate(TaxBase):
    pass


class TaxUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    rate: Decimal | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("rate", mode="before")
    @classmethod
    def _validate_optional_rate(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        dec = Decimal(str(v))
        if dec < Decimal("0.00") or dec > Decimal("100.00"):
            raise ValueError("Tax rate must be between 0 and 100")
        return dec


class TaxPublic(TaxBase):
    id: uuid.UUID
    created_at: datetime


class TaxRuleBase(SQLModel):
    tax_id: uuid.UUID = Field(foreign_key="tax.id", nullable=False, ondelete="CASCADE")
    product_type: ProductType | None = Field(default=None)
    product_id: uuid.UUID | None = Field(default=None, foreign_key="product.id", ondelete="CASCADE")
    priority: int = Field(default=0)

    @model_validator(mode="after")
    def _validate_rule_target(self) -> Self:
        if self.product_type is None and self.product_id is None:
            raise ValueError("At least one of product_type or product_id must be set")
        return self


class TaxRule(TaxRuleBase, table=True):
    __tablename__ = "tax_rule"
    __table_args__ = (
        CheckConstraint(
            "product_type IS NOT NULL OR product_id IS NOT NULL",
            name="ck_tax_rule_target_required",
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class TaxRuleCreate(TaxRuleBase):
    pass


class TaxRuleUpdate(SQLModel):
    tax_id: uuid.UUID | None = None
    product_type: ProductType | None = None
    product_id: uuid.UUID | None = None
    priority: int | None = None


class TaxRulePublic(TaxRuleBase):
    id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Payment Terms
# ---------------------------------------------------------------------------
class PaymentTermBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    due_days: int = Field(default=0, ge=0)
    is_default: bool = Field(default=False)

    @field_validator("due_days", mode="before")
    @classmethod
    def _validate_due_days(cls, v: Any) -> int:
        val = int(v)
        if val < 0:
            raise ValueError("due_days must be greater than or equal to 0")
        return val


class PaymentTerm(PaymentTermBase, table=True):
    __tablename__ = "payment_term"
    __table_args__ = (
        CheckConstraint("due_days >= 0", name="ck_payment_term_due_days_ge_zero"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PaymentTermCreate(PaymentTermBase):
    pass


class PaymentTermUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    due_days: int | None = None
    is_default: bool | None = None

    @field_validator("due_days", mode="before")
    @classmethod
    def _validate_optional_due_days(cls, v: Any) -> int | None:
        if v is None:
            return None
        val = int(v)
        if val < 0:
            raise ValueError("due_days must be greater than or equal to 0")
        return val


class PaymentTermPublic(PaymentTermBase):
    id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Discount Rules
# ---------------------------------------------------------------------------
class DiscountKind(str, Enum):
    percent = "percent"
    fixed = "fixed"


class DiscountScope(str, Enum):
    product = "product"
    subscription = "subscription"


class DiscountProduct(SQLModel, table=True):
    __tablename__ = "discount_product"
    discount_id: uuid.UUID = Field(foreign_key="discount.id", primary_key=True, ondelete="CASCADE")
    product_id: uuid.UUID = Field(foreign_key="product.id", primary_key=True, ondelete="CASCADE")


class DiscountBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    kind: DiscountKind
    value: Decimal = Field(decimal_places=2, max_digits=12)
    scope: DiscountScope
    min_purchase: Decimal | None = Field(default=None, decimal_places=2, max_digits=12)
    min_quantity: int | None = Field(default=None, ge=0)
    start_date: date
    end_date: date
    usage_limit: int | None = Field(default=None)
    is_active: bool = Field(default=True)

    @field_validator("value", mode="before")
    @classmethod
    def _validate_value_type(cls, v: Any) -> Decimal:
        return Decimal(str(v))

    @field_validator("min_purchase", mode="before")
    @classmethod
    def _validate_min_purchase(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        dec = Decimal(str(v))
        if dec < Decimal("0.00"):
            raise ValueError("min_purchase must be non-negative")
        return dec

    @model_validator(mode="after")
    def _validate_discount(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        if self.kind == DiscountKind.percent:
            if self.value < Decimal("0.00") or self.value > Decimal("100.00"):
                raise ValueError("Percent discount value must be between 0 and 100")
        elif self.kind == DiscountKind.fixed:
            if self.value <= Decimal("0.00"):
                raise ValueError("Fixed discount value must be strictly positive")
        if self.usage_limit is not None and self.usage_limit <= 0:
            raise ValueError("usage_limit must be greater than 0")
        return self


class Discount(DiscountBase, table=True):
    __tablename__ = "discount"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_discount_end_date_ge_start"),
        CheckConstraint(
            "(kind = 'percent' AND value >= 0 AND value <= 100) OR (kind = 'fixed' AND value > 0)",
            name="ck_discount_value_valid",
        ),
        CheckConstraint("min_purchase IS NULL OR min_purchase >= 0", name="ck_discount_min_purchase_ge_zero"),
        CheckConstraint("min_quantity IS NULL OR min_quantity >= 0", name="ck_discount_min_quantity_ge_zero"),
        CheckConstraint("usage_limit IS NULL OR usage_limit > 0", name="ck_discount_usage_limit_positive"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    times_used: int = Field(default=0, ge=0)  # read-only
    created_at: datetime = Field(default_factory=get_datetime_utc)
    products: list[Product] = Relationship(link_model=DiscountProduct)


class DiscountCreate(DiscountBase):
    product_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_scope_products(self) -> Self:
        if self.scope == DiscountScope.product and not self.product_ids:
            raise ValueError("discount_product links are required when scope is product")
        if self.scope == DiscountScope.subscription and self.product_ids:
            raise ValueError("discount_product links are forbidden when scope is subscription")
        return self


class DiscountUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    kind: DiscountKind | None = None
    value: Decimal | None = None
    scope: DiscountScope | None = None
    min_purchase: Decimal | None = None
    min_quantity: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    usage_limit: int | None = None
    is_active: bool | None = None
    product_ids: list[uuid.UUID] | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _validate_optional_value(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        return Decimal(str(v))


class DiscountPublic(DiscountBase):
    id: uuid.UUID
    times_used: int
    created_at: datetime
    product_ids: list[uuid.UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Quotation Templates
# ---------------------------------------------------------------------------
class QuotationTemplateLineBase(SQLModel):
    product_id: uuid.UUID = Field(foreign_key="product.id", nullable=False, ondelete="CASCADE")
    variant_id: uuid.UUID | None = Field(default=None, foreign_key="product_variant.id", ondelete="SET NULL")
    quantity: int = Field(default=1, ge=1)

    @field_validator("quantity", mode="before")
    @classmethod
    def _validate_quantity(cls, v: Any) -> int:
        val = int(v)
        if val < 1:
            raise ValueError("quantity must be at least 1")
        return val


class QuotationTemplateLine(QuotationTemplateLineBase, table=True):
    __tablename__ = "quotation_template_line"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_quotation_template_line_quantity_ge_one"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(foreign_key="quotation_template.id", nullable=False, ondelete="CASCADE")
    template: Optional["QuotationTemplate"] = Relationship(back_populates="lines")


class QuotationTemplateLineCreate(QuotationTemplateLineBase):
    pass


class QuotationTemplateLinePublic(QuotationTemplateLineBase):
    id: uuid.UUID
    template_id: uuid.UUID


class QuotationTemplateBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    validity_days: int = Field(default=30, ge=1)
    plan_id: uuid.UUID | None = Field(default=None, foreign_key="plan.id", ondelete="SET NULL")
    is_active: bool = Field(default=True)

    @field_validator("validity_days", mode="before")
    @classmethod
    def _validate_validity_days(cls, v: Any) -> int:
        val = int(v)
        if val < 1:
            raise ValueError("validity_days must be at least 1")
        return val


class QuotationTemplate(QuotationTemplateBase, table=True):
    __tablename__ = "quotation_template"
    __table_args__ = (
        CheckConstraint("validity_days >= 1", name="ck_quotation_template_validity_days_ge_one"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    lines: list[QuotationTemplateLine] = Relationship(back_populates="template", cascade_delete=True)


class QuotationTemplateCreate(QuotationTemplateBase):
    lines: list[QuotationTemplateLineCreate] = Field(default_factory=list)


class QuotationTemplateUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    validity_days: int | None = None
    plan_id: uuid.UUID | None = None
    is_active: bool | None = None
    lines: list[QuotationTemplateLineCreate] | None = None


class QuotationTemplatePublic(QuotationTemplateBase):
    id: uuid.UUID
    created_at: datetime
    lines: list[QuotationTemplateLinePublic] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Template Original Items & Auth Tokens
# ---------------------------------------------------------------------------
# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
