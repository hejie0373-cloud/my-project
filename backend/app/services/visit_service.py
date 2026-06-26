"""
到店记录业务逻辑
"""
import logging
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, Visit
from app.schemas.customer import VisitCreate, VisitOut

logger = logging.getLogger(__name__)


async def create_visit(
    customer_id: str,
    store_id: str,
    data: VisitCreate,
    db: AsyncSession,
) -> Visit:
    """
    录入到店记录
    - 校验客户存在且属于当前店铺
    - 插入 Visit 记录
    """
    # 校验客户
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    if customer.store_id != store_id:
        raise HTTPException(status_code=403, detail="PERMISSION_DENIED")

    # 创建记录
    visit = Visit(
        customer_id=customer_id,
        store_id=store_id,
        visited_at=data.visited_at,
        service_type=data.service_type.strip(),
        staff_name=data.staff_name,
        amount=data.amount,
        payment_method=data.payment_method,
        feedback=data.feedback,
        source="manual",
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)

    logger.info(
        f"到店记录已创建: customer={customer_id}, "
        f"service={visit.service_type}, amount={visit.amount}"
    )

    try:
        from app.tasks.scoring_task import recalculate_for_customer
        recalculate_for_customer.delay(customer_id)
    except Exception as exc:
        logger.warning("评分任务触发失败 customer=%s: %s", customer_id, exc)

    return visit


async def get_visit_list(
    customer_id: str,
    store_id: str,
    db: AsyncSession,
    limit: int = 50,
) -> List[Visit]:
    """
    获取客户的到店记录列表
    """
    result = await db.execute(
        select(Visit)
        .where(
            Visit.customer_id == customer_id,
            Visit.store_id == store_id,
        )
        .order_by(desc(Visit.visited_at))
        .limit(limit)
    )
    return list(result.scalars().all())
