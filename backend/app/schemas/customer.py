"""
客户与到店记录 Pydantic Schema
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Literal

from pydantic import BaseModel, EmailStr, field_validator
import re


# ============================================================
# 客户
# ============================================================

class CustomerCreate(BaseModel):
    """创建客户"""
    name: str
    phone: str
    email: Optional[EmailStr] = None
    gender: Literal["male", "female", "unknown"] = "unknown"
    birthday: Optional[date] = None
    address: Optional[str] = None
    preferred_contact: Literal["sms", "email", "wechat"] = "sms"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1 or len(v) > 100:
            raise ValueError("姓名长度需在 1-100 之间")
        return v


class CustomerUpdate(BaseModel):
    """更新客户（所有字段可选）"""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    gender: Optional[Literal["male", "female", "unknown"]] = None
    birthday: Optional[date] = None
    address: Optional[str] = None
    preferred_contact: Optional[Literal["sms", "email", "wechat"]] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 1 or len(v) > 100:
                raise ValueError("姓名长度需在 1-100 之间")
        return v


class AiMetricSummary(BaseModel):
    """AI 评分摘要（嵌套在客户响应中）"""
    churn_score: Optional[float] = None
    clv: Optional[float] = None
    recommendation: Optional[str] = None
    dimensions: dict = {}
    computed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CustomerOut(BaseModel):
    """客户详情响应"""
    id: str
    store_id: str
    name: str
    phone: str
    email: Optional[str] = None
    gender: str
    birthday: Optional[date] = None
    address: Optional[str] = None
    preferred_contact: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    ai_metric: Optional[AiMetricSummary] = None
    recent_visits: List["VisitOut"] = []
    visit_count: int = 0

    model_config = {"from_attributes": True}


class CustomerListItem(BaseModel):
    """客户列表项"""
    id: str
    name: str
    phone: str
    gender: str
    churn_score: Optional[float] = None
    clv: Optional[float] = None
    last_visited_at: Optional[datetime] = None
    visit_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    """客户列表分页响应"""
    items: List[CustomerListItem]
    total: int
    page: int
    page_size: int


# ============================================================
# 到店记录
# ============================================================

class VisitCreate(BaseModel):
    """录入到店记录"""
    visited_at: datetime
    service_type: str
    staff_name: Optional[str] = None
    amount: float = 0.0
    payment_method: Optional[str] = None
    feedback: Optional[str] = None

    @field_validator("service_type")
    @classmethod
    def validate_service_type(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1 or len(v) > 100:
            raise ValueError("服务类型长度需在 1-100 之间")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("消费金额不能为负数")
        return round(v, 2)


class VisitOut(BaseModel):
    """到店记录响应"""
    id: str
    customer_id: str
    store_id: str
    visited_at: datetime
    service_type: str
    staff_name: Optional[str] = None
    amount: float
    payment_method: Optional[str] = None
    feedback: Optional[str] = None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# CSV 导入
# ============================================================

class ImportProgress(BaseModel):
    """CSV 导入进度"""
    task_id: str
    total: int = 0
    success: int = 0
    failed: int = 0
    status: Literal["processing", "done", "error"] = "processing"
    errors: List[dict] = []
