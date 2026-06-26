from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


PlanCode = Literal["free", "basic", "professional"]
PaymentProvider = Literal["mock", "wechat_pay", "alipay", "stripe"]


class PlanOut(BaseModel):
    code: PlanCode
    name: str
    price_cents: int
    customer_limit: int
    ai_daily_limit: int = 0
    campaign_daily_limit: int = 0
    has_export: bool = False


class SubscriptionOut(BaseModel):
    store_id: str
    plan_name: str
    plan_display_name: Optional[str] = None
    status: str
    customer_limit: int = 1000
    ai_used_today: int = 0
    ai_daily_limit: int = 0
    campaign_used_today: int = 0
    campaign_daily_limit: int = 0
    has_export: bool = False
    next_billing_date: Optional[date] = None
    payment_method: Optional[str] = None
    is_active: bool


class CreateOrderRequest(BaseModel):
    plan_name: PlanCode
    provider: PaymentProvider = "mock"


class PaymentOrderOut(BaseModel):
    id: str
    store_id: str
    plan_name: str
    provider: str
    status: str
    amount_cents: int
    currency: str
    checkout_url: Optional[str] = None
    provider_order_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminPaymentSummaryOut(BaseModel):
    today_revenue_cents: int
    month_revenue_cents: int
    paid_orders: int
    pending_orders: int
    failed_orders: int
    plan_counts: dict[str, int]
    status_counts: dict[str, int]


class AdminSubscriptionUpdate(BaseModel):
    plan_name: Optional[PlanCode] = None
    status: Optional[str] = None
    customer_limit: Optional[int] = Field(default=None, ge=0)
    next_billing_date: Optional[date] = None
