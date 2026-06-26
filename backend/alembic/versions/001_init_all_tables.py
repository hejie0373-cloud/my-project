"""init all tables

Revision ID: 001
Revises:
Create Date: 2026-06-22

此迁移创建「客留」平台全部 11 张数据表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # 1. roles — 角色表
    # ============================================================
    op.create_table(
        "roles",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("name", sa.String(50), nullable=False, comment="角色名称"),
        sa.Column("description", sa.String(255), nullable=True, comment="角色描述"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 2. users — 用户表
    # ============================================================
    op.create_table(
        "users",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=True, comment="用户姓名"),
        sa.Column("phone", sa.String(20), nullable=True, comment="手机号"),
        sa.Column("email", sa.String(255), nullable=True, comment="邮箱"),
        sa.Column("password_hash", sa.String(255), nullable=True, comment="bcrypt 密码哈希"),
        sa.Column("avatar_url", sa.String(500), nullable=True, comment="头像 URL"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE"), comment="是否启用"),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE"), comment="两步验证"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("email"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 3. stores — 店铺表
    # ============================================================
    op.create_table(
        "stores",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, comment="店铺名称"),
        sa.Column("address", sa.String(500), nullable=True, comment="店铺地址"),
        sa.Column("industry_type", sa.String(50), nullable=True, comment="行业类型"),
        sa.Column("logo_url", sa.String(500), nullable=True, comment="Logo URL"),
        sa.Column("owner_id", mysql.CHAR(32), nullable=True, comment="店主用户 ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 4. user_roles — 用户角色关联表
    # ============================================================
    op.create_table(
        "user_roles",
        sa.Column("user_id", mysql.CHAR(32), nullable=False),
        sa.Column("role_id", mysql.CHAR(32), nullable=False),
        sa.Column("store_id", mysql.CHAR(32), nullable=True, comment="super_admin 无 store"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "role_id", "store_id"),
        sa.UniqueConstraint("user_id", "role_id", "store_id", name="uq_user_role_store"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # ============================================================
    # 5. customers — 客户表
    # ============================================================
    op.create_table(
        "customers",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("store_id", mysql.CHAR(32), nullable=False, comment="所属店铺"),
        sa.Column("name", sa.String(100), nullable=False, comment="客户姓名"),
        sa.Column("phone", sa.String(20), nullable=False, comment="手机号"),
        sa.Column("email", sa.String(255), nullable=True, comment="邮箱"),
        sa.Column("gender", mysql.ENUM("male", "female", "unknown"), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("birthday", sa.Date(), nullable=True, comment="生日"),
        sa.Column("address", sa.String(500), nullable=True, comment="地址"),
        sa.Column("preferred_contact", mysql.ENUM("sms", "email", "wechat"), nullable=False, server_default=sa.text("'sms'")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE"), comment="软删除标记"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_customers_store_deleted", "customers", ["store_id", "is_deleted"])
    op.create_index("idx_customers_phone", "customers", ["phone"])
    op.create_index("ix_customers_store_id", "customers", ["store_id"])

    # ============================================================
    # 6. visits — 到店记录表
    # ============================================================
    op.create_table(
        "visits",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("customer_id", mysql.CHAR(32), nullable=False, comment="客户"),
        sa.Column("store_id", mysql.CHAR(32), nullable=False, comment="店铺"),
        sa.Column("visited_at", sa.DateTime(), nullable=False, comment="到店时间"),
        sa.Column("service_type", sa.String(100), nullable=False, comment="服务类型"),
        sa.Column("staff_name", sa.String(100), nullable=True, comment="服务员工"),
        sa.Column("amount", mysql.DECIMAL(10, 2), nullable=False, server_default=sa.text("0.00"), comment="消费金额"),
        sa.Column("payment_method", sa.String(50), nullable=True, comment="支付方式"),
        sa.Column("feedback", sa.Text(), nullable=True, comment="客户反馈"),
        sa.Column("source", mysql.ENUM("manual", "csv", "pos"), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_visits_store_visited", "visits", ["store_id", "visited_at"])
    op.create_index("idx_visits_customer", "visits", ["customer_id"])
    op.create_index("ix_visits_customer_id", "visits", ["customer_id"])
    op.create_index("ix_visits_store_id", "visits", ["store_id"])
    op.create_index("ix_visits_visited_at", "visits", ["visited_at"])

    # ============================================================
    # 7. ai_metrics — AI 客户指标表
    # ============================================================
    op.create_table(
        "ai_metrics",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("customer_id", mysql.CHAR(32), nullable=False, comment="客户"),
        sa.Column("store_id", mysql.CHAR(32), nullable=False, comment="店铺"),
        sa.Column("churn_score", sa.Float(), nullable=True, comment="流失风险评分 0-100"),
        sa.Column("clv", sa.Float(), nullable=True, comment="客户终身价值"),
        sa.Column("recommendation", sa.Text(), nullable=True, comment="AI 推荐行动"),
        sa.Column("alert_sent", sa.Boolean(), nullable=False, server_default=sa.text("FALSE"), comment="是否已预警"),
        sa.Column("computed_at", sa.DateTime(), nullable=True, comment="最近评分时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_ai_metrics_customer_id", "ai_metrics", ["customer_id"])
    op.create_index("ix_ai_metrics_store_id", "ai_metrics", ["store_id"])

    # ============================================================
    # 8. campaigns — 营销活动表
    # ============================================================
    op.create_table(
        "campaigns",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("store_id", mysql.CHAR(32), nullable=False, comment="店铺"),
        sa.Column("name", sa.String(200), nullable=False, comment="活动名称"),
        sa.Column("template", sa.Text(), nullable=False, comment="消息模板"),
        sa.Column("channels", mysql.JSON(), nullable=False, comment="发送渠道"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True, comment="预约发送时间"),
        sa.Column("status", mysql.ENUM("draft", "scheduled", "sent", "failed"), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_by", mysql.CHAR(32), nullable=True, comment="创建人"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_campaigns_store", "campaigns", ["store_id"])

    # ============================================================
    # 9. campaign_logs — 活动发送日志表
    # ============================================================
    op.create_table(
        "campaign_logs",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("campaign_id", mysql.CHAR(32), nullable=False, comment="活动"),
        sa.Column("customer_id", mysql.CHAR(32), nullable=False, comment="客户"),
        sa.Column("channel", mysql.ENUM("sms", "email", "wechat"), nullable=False, comment="渠道"),
        sa.Column("status", mysql.ENUM("pending", "sent", "failed"), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("sent_at", sa.DateTime(), nullable=True, comment="发送时间"),
        sa.Column("response", sa.Text(), nullable=True, comment="发送响应"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_campaign_logs_campaign", "campaign_logs", ["campaign_id"])
    op.create_index("idx_campaign_logs_customer", "campaign_logs", ["customer_id"])

    # ============================================================
    # 10. integrations — 第三方集成配置表
    # ============================================================
    op.create_table(
        "integrations",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("store_id", mysql.CHAR(32), nullable=False, comment="店铺"),
        sa.Column("type", mysql.ENUM("sms", "email", "wechat", "pos", "oauth"), nullable=False, comment="集成类型"),
        sa.Column("credentials", mysql.JSON(), nullable=False, comment="凭据 JSON"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE"), comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_integrations_store", "integrations", ["store_id"])

    # ============================================================
    # 11. subscriptions — 订阅表
    # ============================================================
    op.create_table(
        "subscriptions",
        sa.Column("id", mysql.CHAR(32), nullable=False),
        sa.Column("store_id", mysql.CHAR(32), nullable=False, comment="店铺"),
        sa.Column("plan_name", mysql.ENUM("basic", "professional", "enterprise"), nullable=False, server_default=sa.text("'basic'")),
        sa.Column("customer_limit", mysql.CHAR(32), nullable=True, comment="客户数上限"),
        sa.Column("next_billing_date", sa.Date(), nullable=True, comment="下次扣款日期"),
        sa.Column("payment_method", mysql.ENUM("wechat_pay", "alipay", "stripe"), nullable=True),
        sa.Column("status", mysql.ENUM("active", "overdue", "cancelled", "trial"), nullable=False, server_default=sa.text("'trial'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    """按依赖顺序反向删除所有表"""
    op.drop_table("subscriptions")
    op.drop_table("integrations")
    op.drop_table("campaign_logs")
    op.drop_table("campaigns")
    op.drop_table("ai_metrics")
    op.drop_table("visits")
    op.drop_table("customers")
    op.drop_table("user_roles")
    op.drop_table("stores")
    op.drop_table("users")
    op.drop_table("roles")
