"""
超级管理员路由（仅 super_admin 可访问）
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Role
from app.models.store import Store
from app.models.customer import Customer
from app.models.payment import PaymentOrder
from app.models.subscription import Subscription
from app.models.ai_metric import AiMetric
from app.schemas.billing import AdminPaymentSummaryOut, AdminSubscriptionUpdate, PaymentOrderOut
from app.services.billing_service import (
    _get_or_create_sub as ensure_subscription,
    get_plan,
    list_admin_orders,
    subscription_is_active,
)

router = APIRouter()


async def _require_super_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(Role.name).join(UserRole).where(UserRole.user_id == current_user.id)
    )
    if "super_admin" not in {r[0] for r in result.all()}:
        raise HTTPException(403, "PERMISSION_DENIED")
    return current_user


def _subscription_payload(subscription: Subscription | None) -> dict | None:
    if not subscription:
        return None
    plan = get_plan(subscription.plan_name)
    return {
        "plan": subscription.plan_name,
        "plan_name": subscription.plan_name,
        "plan_display_name": plan["name"],
        "status": subscription.status,
        "customer_limit": subscription.customer_limit or plan["customer_limit"],
        "ai_used_today": subscription.ai_used_today or 0,
        "ai_daily_limit": int(plan["ai_daily_limit"]),
        "campaign_used_today": subscription.campaign_used_today or 0,
        "campaign_daily_limit": int(plan["campaign_daily_limit"]),
        "has_export": bool(plan.get("has_export")),
        "restrictions": subscription.restrictions or "",
        "next_billing_date": subscription.next_billing_date,
        "is_active": subscription_is_active(subscription),
    }


@router.get("/overview", summary="平台总览")
async def admin_overview(
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    stores = (await db.execute(
        select(func.count(Store.id)).where(Store.id != "00000000000000000000000000000001")
    )).scalar() or 0
    users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    customers = (await db.execute(
        select(func.count(Customer.id)).where(Customer.is_deleted == False)  # noqa
    )).scalar() or 0
    high_risk = (await db.execute(
        select(func.count(AiMetric.id)).where(AiMetric.churn_score > 60)
    )).scalar() or 0
    return {"total_stores": stores, "total_users": users, "total_customers": customers, "high_risk_customers": high_risk}


@router.get("/stores", summary="店铺列表")
async def admin_stores(
    _admin: User = Depends(_require_super_admin),
    search: Optional[str] = Query(None, description="搜索店铺名/店主名/手机号"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    sys_store_id = "00000000000000000000000000000001"
    base = select(Store).where(Store.id != sys_store_id)
    count_base = select(func.count(Store.id)).where(Store.id != sys_store_id)

    # 搜索：MySQL LIKE
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        # 通过 owner 子查询匹配
        owner_match = select(User.id).where(
            or_(User.name.like(pattern), User.phone.like(pattern))
        ).scalar_subquery()
        base = base.where(
            or_(Store.name.like(pattern), Store.owner_id.in_(owner_match))
        )
        count_base = count_base.where(
            or_(Store.name.like(pattern), Store.owner_id.in_(owner_match))
        )

    count = (await db.execute(count_base)).scalar() or 0
    result = await db.execute(
        base.order_by(Store.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    stores = result.scalars().all()
    items = []
    for s in stores:
        owner_result = await db.execute(select(User).where(User.id == s.owner_id))
        owner = owner_result.scalar_one_or_none()
        sub_result = await db.execute(select(Subscription).where(Subscription.store_id == s.id))
        sub = sub_result.scalar_one_or_none()
        items.append({
            "id": s.id, "name": s.name, "industry_type": s.industry_type,
            "address": s.address, "created_at": str(s.created_at),
            "owner_name": owner.name if owner else None,
            "owner_phone": owner.phone if owner else None,
            "subscription": _subscription_payload(sub),
        })
    return {"items": items, "total": count, "page": page, "page_size": page_size}


@router.get("/users", summary="用户列表")
async def admin_users(
    _admin: User = Depends(_require_super_admin),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    result = await db.execute(select(User).offset((page - 1) * page_size).limit(page_size))
    users = result.scalars().all()
    items = []
    for u in users:
        roles_result = await db.execute(
            select(Role.name).join(UserRole).where(UserRole.user_id == u.id)
        )
        roles = [r[0] for r in roles_result.all()]
        items.append({
            "id": u.id, "name": u.name, "phone": u.phone, "email": getattr(u, "email", None),
            "is_active": u.is_active, "roles": roles, "created_at": str(u.created_at),
        })
    return {"items": items, "total": count, "page": page, "page_size": page_size}


@router.get("/payment-orders", summary="支付订单列表")
async def admin_payment_orders(
    _admin: User = Depends(_require_super_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    orders, total = await list_admin_orders(db, page, page_size, status_filter)
    items = []
    for order in orders:
        store = (await db.execute(select(Store).where(Store.id == order.store_id))).scalar_one_or_none()
        payload = PaymentOrderOut.model_validate(order).model_dump()
        payload["store_name"] = store.name if store else None
        items.append(payload)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/payment-summary", response_model=AdminPaymentSummaryOut, summary="支付概览")
async def admin_payment_summary(
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    today_start = datetime.combine(date.today(), datetime.min.time())
    month_start = datetime.combine(date.today().replace(day=1), datetime.min.time())

    today_revenue = (await db.execute(
        select(func.coalesce(func.sum(PaymentOrder.amount_cents), 0)).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= today_start,
        )
    )).scalar() or 0
    month_revenue = (await db.execute(
        select(func.coalesce(func.sum(PaymentOrder.amount_cents), 0)).where(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= month_start,
        )
    )).scalar() or 0

    paid_orders = (await db.execute(
        select(func.count(PaymentOrder.id)).where(PaymentOrder.status == "paid")
    )).scalar() or 0
    pending_orders = (await db.execute(
        select(func.count(PaymentOrder.id)).where(PaymentOrder.status == "pending")
    )).scalar() or 0
    failed_orders = (await db.execute(
        select(func.count(PaymentOrder.id)).where(PaymentOrder.status == "failed")
    )).scalar() or 0

    plan_rows = (await db.execute(
        select(Subscription.plan_name, func.count(Subscription.id)).group_by(Subscription.plan_name)
    )).all()
    status_rows = (await db.execute(
        select(Subscription.status, func.count(Subscription.id)).group_by(Subscription.status)
    )).all()

    return AdminPaymentSummaryOut(
        today_revenue_cents=int(today_revenue),
        month_revenue_cents=int(month_revenue),
        paid_orders=int(paid_orders),
        pending_orders=int(pending_orders),
        failed_orders=int(failed_orders),
        plan_counts={name: int(count) for name, count in plan_rows},
        status_counts={status: int(count) for status, count in status_rows},
    )


@router.get("/stores/{store_id}/payment-orders", summary="店铺支付订单")
async def admin_store_payment_orders(
    store_id: str,
    _admin: User = Depends(_require_super_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    count = (await db.execute(
        select(func.count(PaymentOrder.id)).where(PaymentOrder.store_id == store_id)
    )).scalar() or 0
    result = await db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.store_id == store_id)
        .order_by(PaymentOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [PaymentOrderOut.model_validate(order).model_dump() for order in result.scalars().all()]
    return {"items": items, "total": count, "page": page, "page_size": page_size}


@router.put("/stores/{store_id}/subscription", summary="调整店铺订阅")
async def update_store_subscription(
    store_id: str,
    data: AdminSubscriptionUpdate,
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(404, "STORE_NOT_FOUND")

    subscription = await ensure_subscription(store_id, db)
    fields_set = data.model_fields_set

    if data.plan_name is not None:
        plan = get_plan(data.plan_name)
        subscription.plan_name = data.plan_name
        subscription.customer_limit = plan["customer_limit"]
        subscription.quota_date = date.today()
        subscription.ai_used_today = 0
        subscription.campaign_used_today = 0
    if data.status is not None:
        subscription.status = data.status
    if "customer_limit" in fields_set and data.customer_limit is not None:
        subscription.customer_limit = data.customer_limit
    if "next_billing_date" in fields_set:
        subscription.next_billing_date = data.next_billing_date
    if subscription.status == "active" and not subscription.next_billing_date:
        subscription.next_billing_date = date.today() + timedelta(days=30)

    await db.commit()
    await db.refresh(subscription)
    return _subscription_payload(subscription)


@router.put("/users/{user_id}/toggle", summary="启用/禁用用户")
async def toggle_user(
    user_id: str,
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_active = not user.is_active
    await db.commit()
    return {"user_id": user_id, "is_active": user.is_active, "message": "已更新"}


@router.delete("/users/{user_id}", summary="删除用户")
async def delete_user(
    user_id: str,
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    # 检查唯一管理员
    rr = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
    user_roles = rr.scalars().all()
    role_result = await db.execute(select(Role).where(Role.id.in_([ur.role_id for ur in user_roles])))
    role_names = [r.name for r in role_result.scalars().all()]
    if "super_admin" in role_names:
        raise HTTPException(400, "不能删除系统管理员")
    # 级联删除
    await db.execute(text("DELETE FROM user_roles WHERE user_id = :uid"), {"uid": user_id})
    await db.delete(user)
    await db.commit()
    return {"message": "用户已删除"}


@router.get("/stores/{store_id}", summary="店铺详情")
async def admin_store_detail(
    store_id: str,
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """查看单个店铺的详细信息：店主、店员、客户列表"""
    store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(404, "店铺不存在")

    # 店主
    owner_result = await db.execute(
        select(User).join(UserRole).where(UserRole.store_id == store_id, UserRole.role_id == select(Role.id).where(Role.name == "store_owner").scalar_subquery())
    )
    owner = owner_result.scalar_one_or_none()

    # 店员列表
    staff_result = await db.execute(
        select(User).join(UserRole).where(UserRole.store_id == store_id, UserRole.role_id == select(Role.id).where(Role.name == "staff").scalar_subquery())
    )
    staff = staff_result.scalars().all()

    # 客户列表
    cust_result = await db.execute(
        select(Customer).where(Customer.store_id == store_id, Customer.is_deleted == False).limit(100)  # noqa
    )
    customers = cust_result.scalars().all()

    # 订阅
    sub = (await db.execute(select(Subscription).where(Subscription.store_id == store_id))).scalar_one_or_none()

    return {
        "id": store.id, "name": store.name, "industry_type": store.industry_type,
        "address": store.address, "created_at": str(store.created_at),
        "owner": {"id": owner.id, "name": owner.name, "phone": owner.phone, "is_active": owner.is_active} if owner else None,
        "staff": [{"id": s.id, "name": s.name, "phone": s.phone, "is_active": s.is_active} for s in staff],
        "customers": [{"id": c.id, "name": c.name, "phone": c.phone, "gender": c.gender} for c in customers],
        "customer_count": len(customers),
        "subscription": _subscription_payload(sub),
    }


@router.put("/stores/{store_id}/toggle", summary="启用/暂停店铺")
async def toggle_store(
    store_id: str,
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    # 禁用店铺：把所有关联用户的 is_active 设置
    store = (await db.execute(select(Store).where(Store.id == store_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(404, "店铺不存在")

    users_result = await db.execute(
        select(User).join(UserRole).where(UserRole.store_id == store_id)
    )
    store_users = users_result.scalars().all()

    # 切换：如果当前启用则全部禁用，否则全部启用
    new_status = not all(u.is_active for u in store_users) if store_users else True
    for u in store_users:
        u.is_active = new_status
    await db.commit()

    return {"store_id": store_id, "active": new_status, "affected_users": len(store_users), "message": "已更新"}


@router.put("/stores/{store_id}/restrictions", summary="设置店铺功能限制")
async def set_store_restrictions(
    store_id: str,
    _admin: User = Depends(_require_super_admin),
    db: AsyncSession = Depends(get_db),
    restrictions: str = Query("", description="逗号分隔的限制功能，如 ai,campaign,export"),
):
    sub = await ensure_subscription(store_id, db)
    sub.restrictions = restrictions
    await db.commit()
    return {"store_id": store_id, "restrictions": restrictions, "message": "限制已更新"}
