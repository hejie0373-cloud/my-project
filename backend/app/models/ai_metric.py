"""
AI 评分域：AiMetric
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


class AiMetric(Base):
    """AI 客户指标表（每个客户一条记录）"""
    __tablename__ = "ai_metrics"

    id = Column(CHAR(32), primary_key=True, default=lambda: __import__("uuid").uuid4().hex)
    customer_id = Column(CHAR(32), ForeignKey("customers.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    churn_score = Column(Float, nullable=True, comment="流失风险评分 (0-100)")
    clv = Column(Float, nullable=True, comment="客户终身价值 (CLV)")
    recommendation = Column(Text, nullable=True, comment="AI 推荐下一步行动")
    alert_sent = Column(Boolean, default=False, nullable=False, comment="是否已发送流失预警")
    computed_at = Column(DateTime, nullable=True, comment="最近一次评分计算时间")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    customer = relationship("Customer", back_populates="ai_metric")

    def __repr__(self):
        return f"<AiMetric(customer={self.customer_id}, churn={self.churn_score})>"
