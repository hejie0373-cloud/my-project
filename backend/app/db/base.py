"""
SQLAlchemy Base 声明
所有 ORM 模型均继承此 Base
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# 导入所有模型（确保 Alembic 能感知所有表，基类在迁移前被导入）
import app.models.user          # noqa: E402, F401
import app.models.store         # noqa: E402, F401
import app.models.customer      # noqa: E402, F401
import app.models.ai_metric     # noqa: E402, F401
import app.models.campaign      # noqa: E402, F401
import app.models.integration   # noqa: E402, F401
import app.models.subscription  # noqa: E402, F401
import app.models.payment       # noqa: E402, F401
