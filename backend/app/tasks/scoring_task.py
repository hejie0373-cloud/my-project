"""
AI 评分 Celery 任务
"""
import asyncio
import logging

from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def recalculate_for_customer(self, customer_id: str):
    """
    单客户流失评分重算

    被 visit 录入后触发
    """
    logger.info(f"[评分任务] 单客户评分: customer_id={customer_id}")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _run():
        from app.db.session import get_session_factory
        from app.services.ai_service import calculate_churn_score

        async with get_session_factory()() as db:
            result = await calculate_churn_score(customer_id, db)
            return result

    result = loop.run_until_complete(_run())
    logger.info(f"[评分任务] 完成: customer={customer_id}, churn={result.churn_score}")
    return {
        "customer_id": customer_id,
        "churn_score": result.churn_score,
        "clv": result.clv,
    }


@celery_app.task(bind=True)
def batch_score_all_customers(self, store_id: str = None):
    """
    全量批量评分

    - store_id=None: 所有店铺
    - store_id=str: 指定店铺
    """
    scope = f"store_id={store_id}" if store_id else "所有店铺"
    logger.info(f"[评分任务] 批量评分开始: {scope}")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _run():
        from app.db.session import get_session_factory
        from app.models.customer import Customer
        from app.services.ai_service import calculate_churn_score

        scored = 0
        errors = 0

        async with get_session_factory()() as db:
            # 查需要评分的客户
            query = select(Customer).where(Customer.is_deleted == False)  # noqa: E712
            if store_id:
                query = query.where(Customer.store_id == store_id)

            result = await db.execute(query)
            customers = result.scalars().all()

            for customer in customers:
                try:
                    await calculate_churn_score(customer.id, db)
                    scored += 1
                except Exception as e:
                    logger.error(f"评分失败 customer={customer.id}: {e}")
                    errors += 1

            await db.commit()

        return {"scored": scored, "errors": errors}

    result = loop.run_until_complete(_run())
    logger.info(f"[评分任务] 完成: scored={result['scored']}, errors={result['errors']}")
    return result
