"""add wechat login fields

Revision ID: 004
Revises: 003
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("wechat_openid", sa.String(length=64), nullable=True, comment="微信 openid"))
    op.add_column("users", sa.Column("wechat_nickname", sa.String(length=64), nullable=True, comment="微信昵称"))
    op.add_column("users", sa.Column("wechat_avatar", sa.String(length=512), nullable=True, comment="微信头像 URL"))
    op.create_unique_constraint("uq_users_wechat_openid", "users", ["wechat_openid"])
    op.alter_column("payment_orders", "provider_order_id", existing_type=sa.String(length=100), type_=sa.String(length=128))


def downgrade():
    op.alter_column("payment_orders", "provider_order_id", existing_type=sa.String(length=128), type_=sa.String(length=100))
    op.drop_constraint("uq_users_wechat_openid", "users", type_="unique")
    op.drop_column("users", "wechat_avatar")
    op.drop_column("users", "wechat_nickname")
    op.drop_column("users", "wechat_openid")
