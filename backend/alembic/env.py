"""
Alembic 迁移环境配置
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# 将 backend 目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型的 Base metadata（确保 autogenerate 能检测到所有表）
from app.db.base import Base  # noqa: E402
from app.core.config import settings  # noqa: E402

target_metadata = Base.metadata


def get_url():
    """获取数据库 URL：优先从配置文件，fallback 到 settings"""
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    # 将异步 URL 转为同步 URL（Alembic 使用同步引擎）
    sync_url = settings.DB_URL.replace("mysql+aiomysql://", "mysql+pymysql://")
    return sync_url


def run_migrations_offline() -> None:
    """
    离线模式：生成 SQL 脚本而非直接执行
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式：直接连接数据库执行迁移
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
