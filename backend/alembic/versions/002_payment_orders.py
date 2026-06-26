"""add payment orders

Revision ID: 002
Revises: 001
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("store_id", mysql.CHAR(32), nullable=False),
        sa.Column("plan_name", mysql.ENUM("basic", "professional", "enterprise"), nullable=False),
        sa.Column("provider", mysql.ENUM("mock", "wechat_pay", "alipay", "stripe"), nullable=False, server_default="mock"),
        sa.Column("status", mysql.ENUM("pending", "paid", "failed", "cancelled", "expired"), nullable=False, server_default="pending"),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="CNY"),
        sa.Column("checkout_url", sa.String(500), nullable=True),
        sa.Column("provider_order_id", sa.String(100), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_payment_orders_store_id", "payment_orders", ["store_id"])
    op.execute(
        """
        INSERT IGNORE INTO subscriptions
            (id, store_id, plan_name, status, created_at, updated_at)
        SELECT REPLACE(UUID(), '-', ''), stores.id, 'basic', 'trial', NOW(), NOW()
        FROM stores
        LEFT JOIN subscriptions ON subscriptions.store_id = stores.id
        WHERE subscriptions.id IS NULL
          AND stores.id != '00000000000000000000000000000001'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_payment_orders_store_id", table_name="payment_orders")
    op.drop_table("payment_orders")
