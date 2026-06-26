import uuid
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    return uuid.uuid4().hex


class Subscription(Base):
    """每个店铺一条订阅记录。"""
    __tablename__ = "subscriptions"

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_name = Column(
        Enum("free", "basic", "professional", "enterprise", name="plan_name_enum"),
        default="free",
        nullable=False,
        comment="套餐名称",
    )
    customer_limit = Column(Integer, default=1000, nullable=False, comment="客户数量上限")
    status = Column(
        Enum("active", "overdue", "cancelled", "trial", name="subscription_status_enum"),
        default="active",
        nullable=False,
        comment="订阅状态",
    )
    quota_date = Column(Date, nullable=True, comment="配额统计日期（用于跨日重置）")
    ai_used_today = Column(Integer, default=0, nullable=False, comment="今日 AI 已用次数")
    campaign_used_today = Column(Integer, default=0, nullable=False, comment="今日营销活动已用次数")
    restrictions = Column(String(500), default='', nullable=False, comment="功能限制，逗号分隔，如 ai,campaign,export")
    next_billing_date = Column(Date, nullable=True, comment="下次扣款日期（仅付费套餐）")
    payment_method = Column(
        Enum("wechat_pay", "alipay", "stripe", name="payment_method_enum"),
        nullable=True,
        comment="支付方式",
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    store = relationship("Store", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription(store={self.store_id}, plan={self.plan_name}, status={self.status})>"
