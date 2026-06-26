"""
店铺域：Store
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    return uuid.uuid4().hex


class Store(Base):
    """店铺表"""
    __tablename__ = "stores"

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False, comment="店铺名称")
    address = Column(String(500), nullable=True, comment="店铺地址")
    industry_type = Column(String(50), nullable=True, comment="行业类型：餐饮/美容美发/零售/健身/其他")
    logo_url = Column(String(500), nullable=True, comment="Logo 图片 URL")
    owner_id = Column(CHAR(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="店主用户 ID")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    owner = relationship("User", back_populates="owned_stores", foreign_keys=[owner_id])
    user_roles = relationship("UserRole", back_populates="store", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="store", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="store", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="store", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="store", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Store(name={self.name})>"
