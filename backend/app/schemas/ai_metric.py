"""
AI 指标 Pydantic Schema
"""
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel


# ============================================================
# 请求
# ============================================================

class GenerateCopyRequest(BaseModel):
    """AI 文案生成请求"""
    customer_id: str
    channel: Literal["sms", "email", "wechat"] = "sms"


class BatchScoreRequest(BaseModel):
    """批量评分请求"""
    store_id: Optional[str] = None  # None = 所有店铺


# ============================================================
# 响应
# ============================================================

class ChurnScoreResponse(BaseModel):
    """流失评分响应"""
    customer_id: str
    churn_score: float  # 0-100
    clv: float
    recommendation: str
    dimensions: dict  # 各维度明细
    computed_at: datetime


class ClvResponse(BaseModel):
    """年预估价值响应"""
    customer_id: str
    clv: float
    avg_monthly_spend: float
    retention_months: float
    data_sufficiency: str  # "sufficient" | "insufficient"


class CopyResponse(BaseModel):
    """AI 文案响应"""
    model_config = {"populate_by_name": True}

    customer_id: str
    channel: str
    content: str
    require_confirmation: bool = False
    source: str = "local"  # "dify" | "deepseek" | "local"


class BatchScoreTaskResponse(BaseModel):
    """批量评分任务响应"""
    task_id: str
    message: str
    scope: str  # "all" | "store:{id}"
