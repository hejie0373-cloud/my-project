"""
客户交易域：Customer / Visit
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    return uuid.uuid4().hex


class Customer(Base):
    """客户表"""
    __tablename__ = "customers"
    __table_args__ = (
        Index("idx_customers_store_deleted", "store_id", "is_deleted"),
        Index("idx_customers_phone", "phone"),
    )

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, comment="客户姓名")
    phone = Column(String(20), nullable=False, comment="手机号")
    email = Column(String(255), nullable=True, comment="邮箱")
    gender = Column(
        Enum("male", "female", "unknown", name="gender_enum"),
        default="unknown",
        nullable=False,
        comment="性别",
    )
    birthday = Column(Date, nullable=True, comment="生日")
    address = Column(String(500), nullable=True, comment="地址")
    preferred_contact = Column(
        Enum("sms", "email", "wechat", name="preferred_contact_enum"),
        default="sms",
        nullable=False,
        comment="首选联系方式",
    )
    is_deleted = Column(Boolean, default=False, nullable=False, comment="软删除标记")
    consent_status = Column(
        Enum("granted", "revoked", name="consent_status_enum"),
        default="granted",
        nullable=False,
        comment="客户授权状态：granted=已授权 revoked=已撤回",
    )
    consent_revoked_at = Column(DateTime, nullable=True, comment="授权撤回时间")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    store = relationship("Store", back_populates="customers")
    visits = relationship("Visit", back_populates="customer", cascade="all, delete-orphan", order_by="Visit.visited_at.desc()")
    ai_metric = relationship("AiMetric", back_populates="customer", uselist=False, cascade="all, delete-orphan")
    campaign_logs = relationship("CampaignLog", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer(name={self.name}, phone={self.phone})>"


class Visit(Base):
    """到店记录表"""
    __tablename__ = "visits"
    __table_args__ = (
        Index("idx_visits_store_visited", "store_id", "visited_at"),
        Index("idx_visits_customer", "customer_id"),
    )

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    customer_id = Column(CHAR(32), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    visited_at = Column(DateTime, nullable=False, index=True, comment="到店时间")
    service_type = Column(String(100), nullable=False, comment="服务类型")
    staff_name = Column(String(100), nullable=True, comment="服务员工姓名")
    amount = Column(Numeric(10, 2), nullable=False, default=0, comment="消费金额")
    payment_method = Column(String(50), nullable=True, comment="支付方式")
    feedback = Column(Text, nullable=True, comment="客户反馈")
    source = Column(
        Enum("manual", "csv", "pos", name="visit_source_enum"),
        default="manual",
        nullable=False,
        comment="数据来源",
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联
    customer = relationship("Customer", back_populates="visits")

    def __repr__(self):
        return f"<Visit(customer={self.customer_id}, at={self.visited_at})>"
