"""expand payment checkout url

Revision ID: 005
Revises: 004
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "payment_orders",
        "checkout_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "payment_orders",
        "checkout_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
