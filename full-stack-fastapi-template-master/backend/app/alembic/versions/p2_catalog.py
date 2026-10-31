"""Phase 2: Catalog and Commercial Configuration

Revision ID: p2_catalog
Revises: p1_roles_audit
Create Date: 2026-10-31 16:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'p2_catalog'
down_revision = 'p1_roles_audit'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Product table
    op.create_table(
        'product',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('type', sa.Enum('software', 'addon', 'service', 'physical', name='producttype'), nullable=False),
        sa.Column('sales_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('sales_price >= 0', name='ck_product_sales_price_ge_zero'),
        sa.CheckConstraint('cost_price >= 0', name='ck_product_cost_price_ge_zero'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_name'), 'product', ['name'], unique=False)
    op.create_index(op.f('ix_product_is_active'), 'product', ['is_active'], unique=False)

    # 2. Product Variant table
    op.create_table(
        'product_variant',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('attribute', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('extra_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint('extra_price >= 0', name='ck_product_variant_extra_price_ge_zero'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'attribute', 'value', name='uq_product_variant_attr_val'),
    )

    # 3. Plan table
    op.create_table(
        'plan',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('billing_period', sa.Enum('daily', 'weekly', 'monthly', 'yearly', name='billingperiod'), nullable=False),
        sa.Column('min_quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('available_from', sa.Date(), nullable=False),
        sa.Column('available_to', sa.Date(), nullable=True),
        sa.Column('auto_close', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('closable', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('pausable', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('renewable', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('price >= 0', name='ck_plan_price_ge_zero'),
        sa.CheckConstraint('min_quantity >= 1', name='ck_plan_min_quantity_ge_one'),
        sa.CheckConstraint('available_to IS NULL OR available_to >= available_from', name='ck_plan_available_to_ge_from'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 4. Tax table
    op.create_table(
        'tax',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('rate >= 0 AND rate <= 100', name='ck_tax_rate_range'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 5. Tax Rule table
    op.create_table(
        'tax_rule',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tax_id', sa.Uuid(), nullable=False),
        sa.Column('product_type', sa.Enum('software', 'addon', 'service', 'physical', name='producttype'), nullable=True),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint('product_type IS NOT NULL OR product_id IS NOT NULL', name='ck_tax_rule_target_required'),
        sa.ForeignKeyConstraint(['tax_id'], ['tax.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 6. Payment Term table
    op.create_table(
        'payment_term',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('due_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('due_days >= 0', name='ck_payment_term_due_days_ge_zero'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 7. Discount table
    op.create_table(
        'discount',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('kind', sa.Enum('percent', 'fixed', name='discountkind'), nullable=False),
        sa.Column('value', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('scope', sa.Enum('product', 'subscription', name='discountscope'), nullable=False),
        sa.Column('min_purchase', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('min_quantity', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('times_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('end_date >= start_date', name='ck_discount_end_date_ge_start'),
        sa.CheckConstraint(
            "(kind = 'percent' AND value >= 0 AND value <= 100) OR (kind = 'fixed' AND value > 0)",
            name='ck_discount_value_valid',
        ),
        sa.CheckConstraint('min_purchase IS NULL OR min_purchase >= 0', name='ck_discount_min_purchase_ge_zero'),
        sa.CheckConstraint('min_quantity IS NULL OR min_quantity >= 0', name='ck_discount_min_quantity_ge_zero'),
        sa.CheckConstraint('usage_limit IS NULL OR usage_limit > 0', name='ck_discount_usage_limit_positive'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 8. Discount Product table
    op.create_table(
        'discount_product',
        sa.Column('discount_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['discount_id'], ['discount.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('discount_id', 'product_id'),
    )

    # 9. Quotation Template table
    op.create_table(
        'quotation_template',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('validity_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('plan_id', sa.Uuid(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('validity_days >= 1', name='ck_quotation_template_validity_days_ge_one'),
        sa.ForeignKeyConstraint(['plan_id'], ['plan.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 10. Quotation Template Line table
    op.create_table(
        'quotation_template_line',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('template_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('variant_id', sa.Uuid(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint('quantity >= 1', name='ck_quotation_template_line_quantity_ge_one'),
        sa.ForeignKeyConstraint(['template_id'], ['quotation_template.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variant.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('quotation_template_line')
    op.drop_table('quotation_template')
    op.drop_table('discount_product')
    op.drop_table('discount')
    op.drop_table('payment_term')
    op.drop_table('tax_rule')
    op.drop_table('tax')
    op.drop_table('plan')
    op.drop_table('product_variant')
    op.drop_index(op.f('ix_product_is_active'), table_name='product')
    op.drop_index(op.f('ix_product_name'), table_name='product')
    op.drop_table('product')

