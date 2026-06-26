"""
数据库连接池与会话管理（懒加载引擎，避免 import 时触发连接）
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_SessionFactory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """获取引擎（懒初始化）"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DB_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=False,
            echo=settings.DEBUG,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取会话工厂（懒初始化）"""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _SessionFactory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取数据库会话"""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
