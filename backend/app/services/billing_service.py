"""计费服务：套餐定义、配额检查、支付订单。"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentOrder
from app.models.subscription import Subscription
from app.schemas.billing import PlanOut
from app.services.alipay_service import build_return_url, create_page_pay_url, query_trade, verify_notify, verify_return

# ============================================================
# 套餐定义
# ============================================================

PLANS: dict[str, dict] = {
    "free": {
        "code": "free",
        "name": "免费版",
        "price_cents": 0,
        "customer_limit": 1000,
        "ai_daily_limit": 10,
        "campaign_daily_limit": 1,
        "has_export": False,
    },
    "basic": {
        "code": "basic",
        "name": "基础版",
        "price_cents": 1990,
        "customer_limit": 2000,
        "ai_daily_limit": -1,   # 无限
        "campaign_daily_limit": 50,
        "has_export": True,
    },
    "professional": {
        "code": "professional",
        "name": "专业版",
        "price_cents": 4990,
        "customer_limit": 5000,
        "ai_daily_limit": -1,   # 无限
        "campaign_daily_limit": 100,
        "has_export": True,
    },
}

LEGACY_PLAN_ALIASES = {"enterprise": "professional"}


def list_plans() -> list[PlanOut]:
    return [PlanOut(**plan) for plan in PLANS.values()]


def get_plan(plan_name: str) -> dict:
    plan_name = LEGACY_PLAN_ALIASES.get(plan_name, plan_name)
    plan = PLANS.get(plan_name)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PLAN_NOT_FOUND")
    return plan


# ============================================================
# 配额检查
# ============================================================

async def _reset_daily_if_needed(sub: Subscription) -> bool:
    """跨日自动重置每日配额。返回 True 表示发生了重置。"""
    today = date.today()
    if sub.quota_date is None or sub.quota_date != today:
        sub.ai_used_today = 0
        sub.campaign_used_today = 0
        sub.quota_date = today
        return True
    return False


async def check_quota(
    store_id: str,
    db: AsyncSession,
    quota_type: str,  # "ai" | "campaign" | "export" | "customer_add"
) -> Subscription:
    """
    统一的配额检查入口。

    quota_type:
      - "ai":             AI 评分 / 文案生成
      - "campaign":       创建营销活动
      - "export":         CSV 导出
      - "customer_add":   新增客户（检查客户数上限）
    """
    sub = await _get_or_create_sub(store_id, db)

    # 检查功能限制
    if sub.restrictions:
        restricted = set(sub.restrictions.split(","))
        if quota_type in restricted:
            feature_names = {"ai": "AI评分/文案", "campaign": "营销活动", "export": "数据导出"}
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"该功能已被管理员限制：{feature_names.get(quota_type, quota_type)}",
            )

    if sub.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="请先开通套餐",
        )

    plan = get_plan(sub.plan_name)

    # 跨日重置
    await _reset_daily_if_needed(sub)

    if quota_type == "ai":
        limit = int(plan["ai_daily_limit"])
        if limit > 0 and sub.ai_used_today >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"今日 AI 次数已用完（{limit}次/天），请明天再试或升级套餐",
            )
        sub.ai_used_today = (sub.ai_used_today or 0) + 1
        await db.commit()
        return sub

    if quota_type == "campaign":
        limit = int(plan["campaign_daily_limit"])
        if limit > 0 and sub.campaign_used_today >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"今日营销活动次数已用完（{limit}次/天），请明天再试或升级套餐",
            )
        sub.campaign_used_today = (sub.campaign_used_today or 0) + 1
        await db.commit()
        return sub

    if quota_type == "export":
        if not plan.get("has_export"):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="数据导出功能需升级到基础版或专业版",
            )
        return sub

    if quota_type == "customer_add":
        from sqlalchemy import func
        from app.models.customer import Customer
        count_result = await db.execute(
            select(func.count(Customer.id)).where(
                Customer.store_id == store_id,
                Customer.is_deleted == False,  # noqa: E712
            )
        )
        current = count_result.scalar() or 0
        limit = int(plan["customer_limit"])
        if current >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"客户数已达上限（{limit}），请升级套餐",
            )
        return sub

    raise ValueError(f"Unknown quota_type: {quota_type}")


# ============================================================
# 订阅管理
# ============================================================

async def get_subscription(store_id: str, db: AsyncSession) -> Optional[Subscription]:
    result = await db.execute(select(Subscription).where(Subscription.store_id == store_id))
    return result.scalar_one_or_none()


async def _get_or_create_sub(store_id: str, db: AsyncSession) -> Subscription:
    """获取订阅，不存在则创建免费版。"""
    sub = await get_subscription(store_id, db)
    if sub:
        return sub
    sub = Subscription(
        store_id=store_id,
        plan_name="free",
        status="active",
        customer_limit=1000,
        quota_date=date.today(),
        ai_used_today=0,
        campaign_used_today=0,
    )
    db.add(sub)
    await db.flush()
    return sub


# 保持兼容别名
ensure_subscription = _get_or_create_sub


def subscription_is_active(sub: Optional[Subscription]) -> bool:
    if not sub or sub.status != "active":
        return False
    if sub.next_billing_date and sub.next_billing_date < date.today():
        return False
    return True


# ============================================================
# 支付订单
# ============================================================

async def create_order(
    store_id: str,
    plan_name: str,
    provider: str,
    db: AsyncSession,
) -> PaymentOrder:
    plan = get_plan(plan_name)
    if plan["price_cents"] <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="免费版无需支付")
    if provider not in {"mock", "alipay"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PAYMENT_PROVIDER_NOT_CONFIGURED")

    order = PaymentOrder(
        store_id=store_id,
        plan_name=plan_name,
        provider=provider,
        status="pending",
        amount_cents=plan["price_cents"],
        currency="CNY",
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(order)
    await db.flush()
    if provider == "mock":
        order.provider_order_id = f"mock_{order.id}"
        order.checkout_url = "/billing"
    else:
        order.checkout_url = create_page_pay_url(
            order_no=order.id,
            amount_cents=order.amount_cents,
            subject=f"客留{plan['name']}订阅",
            body="客留平台订阅服务",
            return_url=build_return_url(order.id),
        )
    await db.commit()
    await db.refresh(order)
    return order


async def get_order(order_id: str, store_id: str, db: AsyncSession) -> PaymentOrder:
    result = await db.execute(
        select(PaymentOrder).where(PaymentOrder.id == order_id, PaymentOrder.store_id == store_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ORDER_NOT_FOUND")
    return order


async def _get_order_by_id(order_id: str, db: AsyncSession) -> PaymentOrder:
    result = await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ORDER_NOT_FOUND")
    return order


async def mark_order_paid(order_id: str, store_id: str, db: AsyncSession) -> PaymentOrder:
    order = await get_order(order_id, store_id, db)
    if order.status == "paid":
        return order
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ORDER_NOT_PAYABLE")
    if order.expires_at < datetime.utcnow():
        order.status = "expired"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ORDER_EXPIRED")

    return await _activate_paid_order(
        order=order,
        db=db,
        payment_method=None if order.provider == "mock" else order.provider,
    )


async def _activate_paid_order(
    order: PaymentOrder,
    db: AsyncSession,
    payment_method: Optional[str],
    provider_order_id: Optional[str] = None,
) -> PaymentOrder:
    sub = await _get_or_create_sub(order.store_id, db)
    plan = get_plan(order.plan_name)

    order.status = "paid"
    if provider_order_id:
        order.provider_order_id = provider_order_id
    order.paid_at = datetime.utcnow()
    sub.plan_name = order.plan_name
    sub.status = "active"
    sub.customer_limit = plan["customer_limit"]
    sub.quota_date = date.today()
    sub.ai_used_today = 0
    sub.campaign_used_today = 0
    sub.payment_method = payment_method
    sub.next_billing_date = date.today() + timedelta(days=30)

    await db.commit()
    await db.refresh(order)
    return order


async def confirm_alipay_return(
    order_id: str,
    store_id: str,
    data: dict,
    db: AsyncSession,
) -> PaymentOrder:
    order = await get_order(order_id, store_id, db)
    return await _confirm_alipay_return_for_order(order, order_id, data, db)


async def confirm_alipay_return_public(
    order_id: str,
    data: dict,
    db: AsyncSession,
) -> PaymentOrder:
    order = await _get_order_by_id(order_id, db)
    return await _confirm_alipay_return_for_order(order, order_id, data, db)


async def _confirm_alipay_return_for_order(
    order: PaymentOrder,
    order_id: str,
    data: dict,
    db: AsyncSession,
) -> PaymentOrder:
    if not verify_return(data):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ALIPAY_RETURN_VERIFY_FAILED")
    if data.get("out_trade_no") != order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ALIPAY_RETURN_ORDER_MISMATCH")

    if order.provider != "alipay":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ORDER_PROVIDER_MISMATCH")

    try:
        expected_amount = Decimal(order.amount_cents) / Decimal("100")
        actual_amount = Decimal(str(data.get("total_amount")))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ALIPAY_RETURN_AMOUNT_INVALID")
    if actual_amount != expected_amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ALIPAY_RETURN_AMOUNT_MISMATCH")

    if order.status == "paid":
        return order
    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ORDER_NOT_PAYABLE")

    return await _activate_paid_order(
        order=order,
        db=db,
        payment_method="alipay",
        provider_order_id=data.get("trade_no"),
    )


async def sync_alipay_order(order_id: str, store_id: str, db: AsyncSession) -> PaymentOrder:
    order = await get_order(order_id, store_id, db)
    return await _sync_alipay_order(order, db)


async def sync_alipay_order_public(order_id: str, db: AsyncSession) -> PaymentOrder:
    order = await _get_order_by_id(order_id, db)
    return await _sync_alipay_order(order, db)


async def _sync_alipay_order(order: PaymentOrder, db: AsyncSession) -> PaymentOrder:
    if order.provider != "alipay" or order.status != "pending":
        return order

    trade = await query_trade(order.id)
    if not trade or trade.get("code") != "10000":
        return order
    if trade.get("trade_status") not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        return order

    try:
        expected_amount = Decimal(order.amount_cents) / Decimal("100")
        actual_amount = Decimal(str(trade.get("total_amount")))
    except Exception:
        return order
    if actual_amount != expected_amount:
        return order

    return await _activate_paid_order(
        order=order,
        db=db,
        payment_method="alipay",
        provider_order_id=trade.get("trade_no"),
    )


async def handle_alipay_notify(data: dict, db: AsyncSession) -> bool:
    if not verify_notify(data):
        return False
    if data.get("trade_status") not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        return False

    order_id = data.get("out_trade_no")
    result = await db.execute(select(PaymentOrder).where(PaymentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return False
    if order.provider != "alipay":
        return False

    try:
        expected_amount = Decimal(order.amount_cents) / Decimal("100")
        actual_amount = Decimal(str(data.get("total_amount")))
    except Exception:
        return False
    if actual_amount != expected_amount:
        return False

    if order.status == "paid":
        return True
    if order.status != "pending":
        return False

    await _activate_paid_order(
        order=order,
        db=db,
        payment_method="alipay",
        provider_order_id=data.get("trade_no"),
    )
    return True


async def list_admin_orders(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
) -> tuple[list[PaymentOrder], int]:
    from sqlalchemy import func

    query = select(PaymentOrder)
    count_query = select(func.count(PaymentOrder.id))
    if status_filter:
        query = query.where(PaymentOrder.status == status_filter)
        count_query = count_query.where(PaymentOrder.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(desc(PaymentOrder.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total
