import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    return uuid.uuid4().hex


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_name = Column(
        Enum("basic", "professional", "enterprise", name="payment_plan_name_enum"),
        nullable=False,
    )
    provider = Column(
        Enum("mock", "wechat_pay", "alipay", "stripe", name="payment_provider_enum"),
        default="mock",
        nullable=False,
    )
    status = Column(
        Enum("pending", "paid", "failed", "cancelled", "expired", name="payment_order_status_enum"),
        default="pending",
        nullable=False,
    )
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(10), default="CNY", nullable=False)
    checkout_url = Column(Text, nullable=True)
    provider_order_id = Column(String(128), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    store = relationship("Store")

    def __repr__(self):
        return f"<PaymentOrder(id={self.id}, store={self.store_id}, status={self.status})>"
