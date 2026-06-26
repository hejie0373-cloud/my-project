"""
客户业务逻辑：CRUD、搜索、ES 同步
"""
import logging
from datetime import datetime
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.customer import Customer, Visit
from app.models.ai_metric import AiMetric
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerOut,
    CustomerListItem,
    CustomerListResponse,
    AiMetricSummary,
)
from app.utils.es_client import (
    sync_customer_to_es,
    delete_customer_from_es,
    search_customers_in_es,
)

logger = logging.getLogger(__name__)


def _score_from_brackets(value: float, brackets: list[tuple[float, float]]) -> float:
    for threshold, score in brackets:
        if value >= threshold:
            return score
    return 0.0


def _build_ai_dimensions(visits: list[Visit]) -> dict:
    """Build display-only AI dimensions from recent visits."""
    if not visits:
        return {
            "recency_score": 100,
            "frequency_score": 70,
            "trend_score": 40,
            "total_visits": 0,
            "days_ago": 999,
            "monthly_visits": 0,
        }

    recency_brackets = [(float("inf"), 100), (90, 90), (60, 75), (30, 55), (14, 30), (7, 15), (0, 0)]
    frequency_brackets = [(float("inf"), 0), (4, 15), (2, 35), (1, 55), (0.3, 80), (0, 100)]
    trend_brackets = [(float("inf"), 0), (10, 15), (-10, 35), (-30, 65), (float("-inf"), 90)]

    total = len(visits)
    days_ago = (datetime.utcnow() - visits[0].visited_at).days
    active_days = max(1, (datetime.utcnow() - visits[-1].visited_at).days)
    active_months = max(1, active_days // 30)
    monthly_freq = total / active_months

    recency_score = _score_from_brackets(days_ago, recency_brackets)
    frequency_score = 70 if total < 2 else _score_from_brackets(monthly_freq, frequency_brackets)

    if total < 3:
        trend_score = 40
    else:
        recent_3 = visits[:3]
        earlier_3 = visits[3:6] if total >= 6 else visits[3:]
        recent_avg = sum(float(v.amount) for v in recent_3) / len(recent_3)
        earlier_avg = sum(float(v.amount) for v in earlier_3) / len(earlier_3) if earlier_3 else recent_avg
        change_pct = ((recent_avg - earlier_avg) / earlier_avg) * 100 if earlier_avg > 0 else 0
        trend_score = _score_from_brackets(change_pct, trend_brackets)

    return {
        "recency_score": recency_score,
        "recency_weight": 0.4,
        "days_ago": days_ago,
        "frequency_score": frequency_score,
        "frequency_weight": 0.3,
        "monthly_visits": round(monthly_freq, 2),
        "trend_score": trend_score,
        "trend_weight": 0.3,
        "total_visits": total,
    }


# ============================================================
# 列表查询
# ============================================================

async def list_customers(
    store_id: str,
    db: AsyncSession,
    search: Optional[str] = None,
    risk_level: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> CustomerListResponse:
    """
    客户列表（分页 + MySQL 模糊搜索 + 风险筛选）

    风险筛选：
    - high：churn_score > 60
    - medium：30 <= churn_score <= 60
    - low：churn_score < 30
    """
    # --- 构建查询 ---
    # 子查询：每个客户的最新 ai_metric
    ai_sub = (
        select(
            AiMetric.customer_id,
            AiMetric.churn_score,
            AiMetric.clv,
        )
        .where(AiMetric.store_id == store_id)
        .subquery()
    )

    # 最近到店时间子查询
    last_visit_sub = (
        select(
            Visit.customer_id,
            func.max(Visit.visited_at).label("last_visited_at"),
            func.count(Visit.id).label("visit_count"),
        )
        .where(Visit.store_id == store_id)
        .group_by(Visit.customer_id)
        .subquery()
    )

    # 主查询
    query = (
        select(
            Customer.id,
            Customer.name,
            Customer.phone,
            Customer.gender,
            Customer.created_at,
            ai_sub.c.churn_score,
            ai_sub.c.clv,
            last_visit_sub.c.last_visited_at,
            last_visit_sub.c.visit_count,
        )
        .outerjoin(ai_sub, Customer.id == ai_sub.c.customer_id)
        .outerjoin(last_visit_sub, Customer.id == last_visit_sub.c.customer_id)
        .where(
            Customer.store_id == store_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )

    # 搜索：ES 优先（1.5秒超时），不可用则 MySQL LIKE
    search_pattern = None
    if search and search.strip():
        try:
            es_ids = search_customers_in_es(store_id, search.strip(), size=200)
            if es_ids:
                query = query.where(Customer.id.in_(es_ids))
            else:
                search_pattern = f"%{search.strip()}%"
        except Exception:
            search_pattern = f"%{search.strip()}%"

    if search_pattern:
        query = query.where(
            or_(
                Customer.name.like(search_pattern),
                Customer.phone.like(search_pattern),
            )
        )

    # 风险筛选
    if risk_level == "high":
        query = query.where(ai_sub.c.churn_score > 60)
    elif risk_level == "medium":
        query = query.where(and_(ai_sub.c.churn_score >= 30, ai_sub.c.churn_score <= 60))
    elif risk_level == "low":
        query = query.where(ai_sub.c.churn_score < 30)

    # --- 计数 ---
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # --- 分页 ---
    query = query.order_by(desc(Customer.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    # --- 组装响应 ---
    items = []
    for row in rows:
        items.append(CustomerListItem(
            id=row[0],
            name=row[1],
            phone=row[2],
            gender=row[3] or "unknown",
            created_at=row[4],
            churn_score=row[5],
            clv=row[6],
            last_visited_at=row[7],
            visit_count=row[8] or 0,
        ))

    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================
# 客户详情
# ============================================================

async def get_customer_detail(
    customer_id: str,
    store_id: str,
    db: AsyncSession,
) -> CustomerOut:
    """
    客户详情（含 AI 评分 + 最近到店记录）
    校验 store_id 防越权
    """
    # 缓存
    from app.utils.cache import get as cache_get, set as cache_set, TTL_MEDIUM
    cache_key = f"customer_detail:{customer_id}"
    cached = await cache_get(cache_key)
    if cached:
        return CustomerOut(**cached)

    # 查客户
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.ai_metric))
        .where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    if customer.store_id != store_id:
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")

    # 查到店记录（最近 10 条）
    visits_result = await db.execute(
        select(Visit)
        .where(Visit.customer_id == customer_id)
        .order_by(desc(Visit.visited_at))
        .limit(10)
    )
    visits = visits_result.scalars().all()

    # 到店次数
    count_result = await db.execute(
        select(func.count(Visit.id)).where(Visit.customer_id == customer_id)
    )
    visit_count = count_result.scalar() or 0

    # 组装 AI 评分摘要
    ai_summary = None
    if customer.ai_metric:
        ai_summary = AiMetricSummary(
            churn_score=customer.ai_metric.churn_score,
            clv=customer.ai_metric.clv,
            recommendation=customer.ai_metric.recommendation,
            dimensions=_build_ai_dimensions(list(visits)),
            computed_at=customer.ai_metric.computed_at,
        )

    # 组装到店记录
    from app.schemas.customer import VisitOut
    recent_visits = [
        VisitOut(
            id=v.id,
            customer_id=v.customer_id,
            store_id=v.store_id,
            visited_at=v.visited_at,
            service_type=v.service_type,
            staff_name=v.staff_name,
            amount=float(v.amount),
            payment_method=v.payment_method,
            feedback=v.feedback,
            source=v.source,
            created_at=v.created_at,
        )
        for v in visits
    ]

    result = CustomerOut(
        id=customer.id,
        store_id=customer.store_id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        gender=customer.gender,
        birthday=customer.birthday,
        address=customer.address,
        preferred_contact=customer.preferred_contact,
        is_deleted=customer.is_deleted,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        ai_metric=ai_summary,
        recent_visits=recent_visits,
        visit_count=visit_count,
    )
    await cache_set(cache_key, result.model_dump(), TTL_MEDIUM)
    return result


# ============================================================
# 创建客户
# ============================================================

async def create_customer(
    store_id: str,
    data: CustomerCreate,
    db: AsyncSession,
) -> Customer:
    """
    创建客户
    - 同店铺内手机号唯一校验
    - 同步到 ES
    """
    # 唯一性检查
    result = await db.execute(
        select(Customer).where(
            Customer.store_id == store_id,
            Customer.phone == data.phone,
            Customer.is_deleted == False,  # noqa: E712
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该手机号的客户已存在",
        )

    customer = Customer(
        store_id=store_id,
        name=data.name.strip(),
        phone=data.phone,
        email=data.email,
        gender=data.gender,
        birthday=data.birthday,
        address=data.address,
        preferred_contact=data.preferred_contact,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    # 同步到 ES（fire-and-forget）
    sync_customer_to_es(
        customer_id=customer.id,
        name=customer.name,
        phone=customer.phone,
        store_id=customer.store_id,
    )

    logger.info(f"客户已创建: id={customer.id}, name={customer.name}")
    return customer


# ============================================================
# 更新客户
# ============================================================

async def update_customer(
    customer_id: str,
    store_id: str,
    data: CustomerUpdate,
    db: AsyncSession,
) -> Customer:
    """
    更新客户（仅更新非 None 字段）
    """
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    if customer.store_id != store_id:
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")

    # 字段级更新
    update_data = data.model_dump(exclude_unset=True)

    # 如果改了手机号，检查唯一性
    if "phone" in update_data and update_data["phone"] != customer.phone:
        dup_result = await db.execute(
            select(Customer).where(
                Customer.store_id == store_id,
                Customer.phone == update_data["phone"],
                Customer.id != customer_id,
                Customer.is_deleted == False,  # noqa: E712
            )
        )
        if dup_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="该手机号的客户已存在")

    for field, value in update_data.items():
        setattr(customer, field, value)

    await db.commit()
    await db.refresh(customer)

    # 清缓存
    from app.utils.cache import set as cache_set
    await cache_set(f"customer_detail:{customer_id}", None, 1)

    # 同步到 ES
    sync_customer_to_es(
        customer_id=customer.id,
        name=customer.name,
        phone=customer.phone,
        store_id=customer.store_id,
    )

    logger.info(f"客户已更新: id={customer.id}")
    return customer


# ============================================================
# 删除客户（软删除）
# ============================================================

async def delete_customer(
    customer_id: str,
    store_id: str,
    db: AsyncSession,
) -> None:
    """
    软删除客户（is_deleted = True）
    """
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    if customer.store_id != store_id:
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")

    customer.is_deleted = True
    await db.commit()

    delete_customer_from_es(customer_id)
    logger.info(f"客户已软删除: id={customer_id}")


async def revoke_customer_consent(
    customer_id: str,
    store_id: str,
    db: AsyncSession,
) -> Customer:
    """
    撤回客户授权 → 自动软删除 + ES 清理 + 记录时间戳
    适用场景：客户明确表示不需要服务 / 拒绝授权条款
    """
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    if customer.store_id != store_id:
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")

    from datetime import datetime
    customer.consent_status = "revoked"
    customer.consent_revoked_at = datetime.utcnow()
    customer.is_deleted = True
    await db.commit()
    await db.refresh(customer)

    delete_customer_from_es(customer_id)
    logger.info(f"客户授权已撤回并清理: id={customer_id}, phone={customer.phone}")

    return customer
