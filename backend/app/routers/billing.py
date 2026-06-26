from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_store
from app.db.session import get_db
from app.schemas.billing import (
    CreateOrderRequest,
    PaymentOrderOut,
    PlanOut,
    SubscriptionOut,
)
from app.services.billing_service import (
    confirm_alipay_return,
    create_order,
    _get_or_create_sub,
    get_plan,
    get_order,
    list_plans,
    mark_order_paid,
    subscription_is_active,
    sync_alipay_order,
)

router = APIRouter()


@router.get("/plans", response_model=list[PlanOut], summary="套餐列表")
async def plans():
    return list_plans()


@router.get("/subscription", response_model=SubscriptionOut, summary="当前店铺订阅")
async def current_subscription(
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_or_create_sub(store_id, db)
    plan = get_plan(sub.plan_name)
    return SubscriptionOut(
        store_id=store_id,
        plan_name=sub.plan_name,
        plan_display_name=plan["name"],
        status=sub.status,
        customer_limit=sub.customer_limit or plan["customer_limit"],
        ai_used_today=sub.ai_used_today or 0,
        ai_daily_limit=int(plan["ai_daily_limit"]),
        campaign_used_today=sub.campaign_used_today or 0,
        campaign_daily_limit=int(plan["campaign_daily_limit"]),
        has_export=bool(plan.get("has_export")),
        next_billing_date=sub.next_billing_date,
        payment_method=sub.payment_method,
        is_active=subscription_is_active(sub),
    )


@router.post("/orders", response_model=PaymentOrderOut, status_code=201, summary="创建支付订单")
async def create_payment_order(
    data: CreateOrderRequest,
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    return await create_order(store_id, data.plan_name, data.provider, db)


@router.get("/orders/{order_id}", response_model=PaymentOrderOut, summary="查询订单")
async def payment_order(
    order_id: str,
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    return await get_order(order_id, store_id, db)


@router.post("/orders/{order_id}/alipay-return", response_model=PaymentOrderOut, summary="确认支付宝同步回跳")
async def confirm_alipay_return_order(
    order_id: str,
    data: dict,
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    return await confirm_alipay_return(order_id, store_id, data, db)


@router.post("/orders/{order_id}/sync-alipay", response_model=PaymentOrderOut, summary="同步支付宝订单状态")
async def sync_alipay_payment_order(
    order_id: str,
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    return await sync_alipay_order(order_id, store_id, db)


@router.post("/orders/{order_id}/mock-pay", response_model=PaymentOrderOut, summary="开发环境模拟支付")
async def mock_pay_order(
    order_id: str,
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    return await mark_order_paid(order_id, store_id, db)
