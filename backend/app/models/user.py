"""
用户权限域：User / Role / UserRole
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_uuid():
    """生成 UUID4 字符串"""
    return uuid.uuid4().hex


class Role(Base):
    """角色表"""
    __tablename__ = "roles"

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    name = Column(String(50), unique=True, nullable=False, comment="角色名称")
    description = Column(String(255), nullable=True, comment="角色描述")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    user_roles = relationship("UserRole", back_populates="role")

    def __repr__(self):
        return f"<Role(name={self.name})>"


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(CHAR(32), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=True, comment="用户姓名")
    phone = Column(String(20), unique=True, nullable=True, comment="手机号")
    password_hash = Column(String(255), nullable=True, comment="bcrypt 密码哈希")
    avatar_url = Column(String(500), nullable=True, comment="头像 URL")
    wechat_openid = Column(String(64), unique=True, nullable=True, comment="微信 openid")
    wechat_nickname = Column(String(64), nullable=True, comment="微信昵称")
    wechat_avatar = Column(String(512), nullable=True, comment="微信头像 URL")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    totp_enabled = Column(Boolean, default=False, nullable=False, comment="是否开启两步验证")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    owned_stores = relationship("Store", back_populates="owner", foreign_keys="Store.owner_id")

    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone})>"


class UserRole(Base):
    """用户-角色关联表（多对多 + store 维度）"""
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "store_id", name="uq_user_role_store"),
    )

    user_id = Column(CHAR(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(CHAR(32), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    store_id = Column(CHAR(32), ForeignKey("stores.id", ondelete="CASCADE"), nullable=True,
                      comment="super_admin 无 store，其余角色必绑店铺")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="user_roles")
    store = relationship("Store", back_populates="user_roles")

    def __repr__(self):
        return f"<UserRole(user={self.user_id}, role={self.role_id}, store={self.store_id})>"
