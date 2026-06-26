"""
Marketing campaign scheduled dispatch tasks.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def dispatch_campaign(self, campaign_id: str):
    """Dispatch one campaign by id."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _run():
        from app.services.campaign_service import dispatch_campaign_task
        await dispatch_campaign_task(campaign_id)

    loop.run_until_complete(_run())
    logger.info("[Campaign] dispatched campaign=%s", campaign_id)
    return {"campaign_id": campaign_id, "status": "done"}


@celery_app.task(bind=True)
def dispatch_due_campaigns(self):
    """Find scheduled campaigns whose scheduled_at has passed and dispatch them."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def _run():
        from app.db.session import get_session_factory
        from app.models.campaign import Campaign
        from app.services.campaign_service import _dispatch_campaign

        dispatched = 0
        async with get_session_factory()() as db:
            result = await db.execute(
                select(Campaign).where(
                    Campaign.status == "scheduled",
                    Campaign.scheduled_at <= datetime.utcnow(),
                )
            )
            campaigns = result.scalars().all()
            for campaign in campaigns:
                await _dispatch_campaign(campaign.id, db)
                dispatched += 1
        return dispatched

    dispatched = loop.run_until_complete(_run())
    logger.info("[Campaign] dispatched due campaigns=%s", dispatched)
    return {"dispatched": dispatched}
