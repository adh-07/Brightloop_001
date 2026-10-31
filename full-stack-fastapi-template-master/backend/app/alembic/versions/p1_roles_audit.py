"""Phase 1: Roles and Audit Log

Revision ID: p1_roles_audit
Revises: fe56fa70289e
Create Date: 2026-10-31 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'p1_roles_audit'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('role', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False, server_default='customer'))
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('entity_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('diff', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_type'), table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_column('user', 'role')

