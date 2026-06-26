"""
第三方集成域：Integration
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    return uuid.uuid4().hex


class Integration(Base):
    """第三方集成配置表"""
    __tablename__ = "integrations"
    __table_args__ = (
        Index("idx_integrations_store", "store_id"),
    )

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(
        Enum("sms", "email", "wechat", "pos", "oauth", name="integration_type_enum"),
        nullable=False,
        comment="集成类型",
    )
    credentials = Column(JSON, nullable=False, comment="凭据配置（生产环境需 AES 加密）")
    enabled = Column(Boolean, default=False, nullable=False, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    store = relationship("Store", back_populates="integrations")

    def __repr__(self):
        return f"<Integration(store={self.store_id}, type={self.type}, enabled={self.enabled})>"
