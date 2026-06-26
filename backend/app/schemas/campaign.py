"""
营销活动 Pydantic Schema
"""
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, field_validator


# ============================================================
# 请求
# ============================================================

class CampaignCreate(BaseModel):
    """创建营销活动"""
    name: str
    template: str  # 消息模板，支持 {{客户姓名}} 等标签
    channels: List[Literal["sms", "email", "wechat"]]
    scheduled_at: Optional[datetime] = None  # None=立即发送
    target_customer_ids: Optional[List[str]] = None  # 指定客户
    target_risk_level: Optional[Literal["high", "all"]] = None  # 按风险筛选

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1 or len(v) > 200:
            raise ValueError("活动名称长度需在 1-200 之间")
        return v

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("至少选择一个发送渠道")
        return v

    @field_validator("target_customer_ids")
    @classmethod
    def validate_target_ids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 500:
            raise ValueError("单次活动最多选择 500 位客户")
        return v


# ============================================================
# 响应
# ============================================================

class CampaignLogOut(BaseModel):
    """发送日志"""
    id: str
    campaign_id: str
    customer_id: str
    channel: str
    status: str
    sent_at: Optional[datetime] = None
    response: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignLogSummary(BaseModel):
    """发送汇总"""
    total: int = 0
    sent: int = 0
    failed: int = 0
    pending: int = 0


class CampaignOut(BaseModel):
    """营销活动"""
    id: str
    store_id: str
    name: str
    template: str
    channels: List[str]
    scheduled_at: Optional[datetime] = None
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    log_summary: Optional[CampaignLogSummary] = None

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    """活动列表分页"""
    items: List[CampaignOut]
    total: int
    page: int
    page_size: int
