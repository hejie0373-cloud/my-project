"""
营销活动域：Campaign / CampaignLog
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    return uuid.uuid4().hex


class Campaign(Base):
    """营销活动表"""
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("idx_campaigns_store", "store_id"),
    )

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False, comment="活动名称")
    template = Column(Text, nullable=False, comment="消息模板（支持 {{变量}} 标签）")
    channels = Column(JSON, nullable=False, comment="发送渠道列表，如 [\"sms\", \"email\"]")
    scheduled_at = Column(DateTime, nullable=True, comment="预约发送时间（NULL = 立即发送）")
    status = Column(
        Enum("draft", "scheduled", "sent", "failed", name="campaign_status_enum"),
        default="draft",
        nullable=False,
        comment="活动状态",
    )
    created_by = Column(CHAR(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建人")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    store = relationship("Store", back_populates="campaigns")
    creator = relationship("User", foreign_keys=[created_by])
    logs = relationship("CampaignLog", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign(name={self.name}, status={self.status})>"


class CampaignLog(Base):
    """营销活动发送日志表"""
    __tablename__ = "campaign_logs"
    __table_args__ = (
        Index("idx_campaign_logs_campaign", "campaign_id"),
        Index("idx_campaign_logs_customer", "customer_id"),
    )

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    campaign_id = Column(CHAR(32), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(CHAR(32), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(
        Enum("sms", "email", "wechat", name="campaign_log_channel_enum"),
        nullable=False,
        comment="发送渠道",
    )
    status = Column(
        Enum("pending", "sent", "failed", name="campaign_log_status_enum"),
        default="pending",
        nullable=False,
        comment="发送状态",
    )
    sent_at = Column(DateTime, nullable=True, comment="实际发送时间")
    response = Column(Text, nullable=True, comment="发送响应/错误信息")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联
    campaign = relationship("Campaign", back_populates="logs")
    customer = relationship("Customer", back_populates="campaign_logs")

    def __repr__(self):
        return f"<CampaignLog(campaign={self.campaign_id}, channel={self.channel}, status={self.status})>"
