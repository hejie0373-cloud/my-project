"""fix legacy subscription schema

Revision ID: 006
Revises: 005
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    op.execute(
        "ALTER TABLE subscriptions "
        "MODIFY COLUMN plan_name ENUM('free','basic','professional','enterprise') "
        "NOT NULL DEFAULT 'free'"
    )
    op.execute(
        "ALTER TABLE subscriptions "
        "MODIFY COLUMN status ENUM('active','overdue','cancelled','trial') "
        "NOT NULL DEFAULT 'active'"
    )
    op.execute(
        "UPDATE subscriptions "
        "SET customer_limit='1000' "
        "WHERE customer_limit IS NULL OR customer_limit='' OR customer_limit REGEXP '[^0-9]'"
    )
    op.execute(
        "ALTER TABLE subscriptions "
        "MODIFY COLUMN customer_limit INT NOT NULL DEFAULT 1000 COMMENT '客户数量上限'"
    )
    if not _has_column("subscriptions", "quota_date"):
        op.add_column("subscriptions", sa.Column("quota_date", sa.Date(), nullable=True, comment="配额统计日期（用于跨日重置）"))
    if not _has_column("subscriptions", "ai_used_today"):
        op.add_column("subscriptions", sa.Column("ai_used_today", sa.Integer(), nullable=False, server_default="0", comment="今日 AI 已用次数"))
    if not _has_column("subscriptions", "campaign_used_today"):
        op.add_column("subscriptions", sa.Column("campaign_used_today", sa.Integer(), nullable=False, server_default="0", comment="今日营销活动已用次数"))
    if not _has_column("subscriptions", "restrictions"):
        op.add_column("subscriptions", sa.Column("restrictions", sa.String(length=500), nullable=False, server_default="", comment="功能限制，逗号分隔，如 ai,campaign,export"))
    if _has_column("subscriptions", "trial_credits"):
        op.drop_column("subscriptions", "trial_credits")


def downgrade():
    if _has_column("subscriptions", "restrictions"):
        op.drop_column("subscriptions", "restrictions")
    if _has_column("subscriptions", "campaign_used_today"):
        op.drop_column("subscriptions", "campaign_used_today")
    if _has_column("subscriptions", "ai_used_today"):
        op.drop_column("subscriptions", "ai_used_today")
    if _has_column("subscriptions", "quota_date"):
        op.drop_column("subscriptions", "quota_date")
    if not _has_column("subscriptions", "trial_credits"):
        op.add_column("subscriptions", sa.Column("trial_credits", sa.String(length=10), nullable=False, server_default="5", comment="免费体验次数"))
    op.execute(
        "ALTER TABLE subscriptions "
        "MODIFY COLUMN plan_name ENUM('basic','professional','enterprise') "
        "NOT NULL DEFAULT 'basic'"
    )
    op.execute(
        "ALTER TABLE subscriptions "
        "MODIFY COLUMN status ENUM('active','overdue','cancelled') "
        "NOT NULL DEFAULT 'active'"
    )
    op.execute(
        "ALTER TABLE subscriptions "
        "MODIFY COLUMN customer_limit CHAR(32) NULL COMMENT '客户数上限'"
    )
