"""
定时报表与通知任务
"""
import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def send_daily_alerts(self):
    """
    每日流失预警（每天 09:00 触发）

    逻辑：
    1. 查询所有 churn_score > 60 且 alert_sent=False 的客户
    2. 通过 Redis Pub/Sub 推送站内通知
    3. 标记 alert_sent=True
    """
    logger.info("[报表任务] 每日流失预警开始")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _run():
        from app.db.session import get_session_factory
        from app.models.ai_metric import AiMetric
        from app.models.customer import Customer
        from sqlalchemy import select

        async with get_session_factory()() as db:
            result = await db.execute(
                select(AiMetric).where(
                    AiMetric.churn_score > 60,
                    AiMetric.alert_sent == False,  # noqa: E712
                )
            )
            high_risk_metrics = result.scalars().all()

            alert_count = 0
            for metric in high_risk_metrics:
                # 发布 Redis 通知
                try:
                    from app.utils.redis_client import publish
                    await publish(
                        f"notify:{metric.store_id}",
                        {
                            "type": "high_risk_alert",
                            "customer_id": metric.customer_id,
                            "churn_score": metric.churn_score,
                            "timestamp": str(metric.computed_at),
                        },
                    )
                    metric.alert_sent = True
                    alert_count += 1
                except Exception as e:
                    logger.error(f"预警发布失败: customer={metric.customer_id}, {e}")

            await db.commit()
            return alert_count

    result = loop.run_until_complete(_run())
    logger.info(f"[报表任务] 完成: {result} 条预警")
    return {"status": "ok", "alerts_sent": result}


@celery_app.task(bind=True)
def send_weekly_report(self, store_id: str = None):
    """
    每周报表（每周一 08:00 触发）

    TODO: 第 6 层完善报表生成 + 邮件发送
    """
    logger.info(f"[报表任务] 周报: store_id={store_id}")
    return {"status": "ok", "store_id": store_id}
