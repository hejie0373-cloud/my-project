"""
营销活动业务逻辑
"""
import logging
from datetime import datetime
from typing import Optional, List, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.campaign import Campaign, CampaignLog
from app.models.customer import Customer
from app.models.ai_metric import AiMetric
from app.models.store import Store
from app.schemas.campaign import (
    CampaignCreate,
    CampaignOut,
    CampaignLogOut,
    CampaignLogSummary,
    CampaignListResponse,
)
from app.services.notification_service import send_to_customer

logger = logging.getLogger(__name__)

# 模板变量默认值
TEMPLATE_DEFAULTS = {
    "{{客户姓名}}": "亲爱的客户",
    "{{服务项目}}": "我们的服务",
    "{{推荐到店日期}}": "本周内",
    "{{店铺名称}}": "我们的店",
}


async def _get_target_customers(
    store_id: str,
    target_customer_ids: Optional[List[str]],
    target_risk_level: Optional[str],
    db: AsyncSession,
) -> List[Customer]:
    """
    确定目标客户列表

    优先级：target_customer_ids > target_risk_level
    """
    if target_customer_ids:
        # 指定客户 ID 列表
        result = await db.execute(
            select(Customer).where(
                Customer.id.in_(target_customer_ids),
                Customer.store_id == store_id,
                Customer.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    if target_risk_level == "high":
        # 高风险客户
        result = await db.execute(
            select(Customer)
            .join(AiMetric, Customer.id == AiMetric.customer_id)
            .where(
                Customer.store_id == store_id,
                Customer.is_deleted == False,  # noqa: E712
                AiMetric.churn_score > 60,
            )
        )
        return list(result.scalars().all())

    if target_risk_level == "all":
        # 所有客户
        result = await db.execute(
            select(Customer).where(
                Customer.store_id == store_id,
                Customer.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    # 默认：空列表（无目标）
    return []


def _render_template(template: str, customer: Customer, store_name: str) -> str:
    """
    渲染消息模板：替换 {{变量}} 为实际值
    """
    content = template
    content = content.replace("{{客户姓名}}", customer.name or "亲爱的客户")
    content = content.replace("{{店铺名称}}", store_name or "我们的店")

    # 服务项目（取最近一次 visit）
    if "{{服务项目}}" in content:
        content = content.replace("{{服务项目}}", "您的专属服务")
    if "{{推荐到店日期}}" in content:
        from datetime import timedelta
        next_week = datetime.utcnow() + timedelta(days=7)
        content = content.replace("{{推荐到店日期}}", next_week.strftime("%m月%d日"))

    return content


# ============================================================
# 创建活动
# ============================================================

async def create_campaign(
    store_id: str,
    created_by: str,
    data: CampaignCreate,
    db: AsyncSession,
) -> Campaign:
    """
    创建营销活动

    流程：
    1. 创建 Campaign 记录
    2. 确定目标客户
    3. 为每个 (客户 × 渠道) 创建 CampaignLog
    4. 立即发送或预约发送
    """
    # 1. 创建 Campaign
    campaign = Campaign(
        store_id=store_id,
        name=data.name.strip(),
        template=data.template.strip(),
        channels=data.channels,
        scheduled_at=data.scheduled_at,
        status="draft",
        created_by=created_by,
    )
    db.add(campaign)
    await db.flush()

    # 2. 确定目标客户
    customers = await _get_target_customers(
        store_id=store_id,
        target_customer_ids=data.target_customer_ids,
        target_risk_level=data.target_risk_level,
        db=db,
    )

    if not customers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未找到匹配的目标客户",
        )

    # 3. 创建 CampaignLog
    logs_to_add = []
    for customer in customers:
        for channel in data.channels:
            log = CampaignLog(
                campaign_id=campaign.id,
                customer_id=customer.id,
                channel=channel,
                status="pending",
            )
            logs_to_add.append(log)

    db.add_all(logs_to_add)

    # 4. 判断立即还是预约发送
    if data.scheduled_at and data.scheduled_at > datetime.utcnow():
        campaign.status = "scheduled"
        logger.info(
            f"活动已排期: id={campaign.id}, "
            f"scheduled_at={data.scheduled_at}, target_count={len(customers)}"
        )
    else:
        # 立即发送
        campaign.status = "draft"
        await db.commit()
        await db.refresh(campaign)

        # 同步 dispatching（开发阶段）
        await _dispatch_campaign(campaign.id, db)

    await db.commit()
    await db.refresh(campaign)

    logger.info(
        f"活动已创建: id={campaign.id}, name={campaign.name}, "
        f"targets={len(customers)}, channels={data.channels}"
    )
    return campaign


# ============================================================
# 活动派发
# ============================================================

async def _dispatch_campaign(campaign_id: str, db: AsyncSession) -> None:
    """
    执行活动发送

    1. 加载 campaign + pending logs
    2. 逐条渲染模板 → 调用 Provider.send()
    3. 更新 log 状态
    4. 全部完成后更新 campaign.status
    """
    # 加载 campaign
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        logger.error(f"活动不存在: {campaign_id}")
        return

    # 加载 pending logs
    logs_result = await db.execute(
        select(CampaignLog).where(
            CampaignLog.campaign_id == campaign_id,
            CampaignLog.status == "pending",
        )
    )
    pending_logs = list(logs_result.scalars().all())

    if not pending_logs:
        campaign.status = "sent"
        await db.commit()
        return

    logger.info(f"开始派发活动: campaign={campaign_id}, logs={len(pending_logs)}")

    sent_count = 0
    failed_count = 0
    store_result = await db.execute(select(Store).where(Store.id == campaign.store_id))
    store = store_result.scalar_one_or_none()
    store_name = store.name if store else ""

    for log in pending_logs:
        try:
            # 查客户
            cust_result = await db.execute(
                select(Customer).where(Customer.id == log.customer_id)
            )
            customer = cust_result.scalar_one_or_none()
            if not customer:
                log.status = "failed"
                log.response = "客户不存在"
                failed_count += 1
                continue

            # 渲染模板
            content = _render_template(campaign.template, customer, store_name)

            # 获取客户联系方式
            if log.channel == "sms":
                to = customer.phone
            elif log.channel == "email":
                to = customer.email or customer.phone  # fallback
            else:
                to = customer.phone  # wechat 用手机号

            if not to:
                log.status = "failed"
                log.response = "客户无联系方式"
                failed_count += 1
                continue

            # 发送
            success, response = await send_to_customer(
                channel=log.channel,
                to=to,
                content=content,
                store_id=campaign.store_id,
                db=db,
            )

            log.status = "sent" if success else "failed"
            log.response = response
            log.sent_at = datetime.utcnow() if success else None

            if success:
                sent_count += 1
            else:
                failed_count += 1

        except Exception as e:
            logger.error(f"发送失败: log_id={log.id}, error={e}")
            log.status = "failed"
            log.response = str(e)
            failed_count += 1

    # 更新 campaign 状态
    if failed_count == 0:
        campaign.status = "sent"
    elif sent_count == 0:
        campaign.status = "failed"
    else:
        campaign.status = "sent"  # 部分成功也算 sent

    await db.commit()
    logger.info(
        f"活动派发完成: campaign={campaign_id}, "
        f"sent={sent_count}, failed={failed_count}"
    )


async def dispatch_campaign_task(campaign_id: str):
    """
    Celery 任务入口：独立 session 执行派发
    """
    from app.db.session import get_session_factory

    async with get_session_factory()() as db:
        await _dispatch_campaign(campaign_id, db)
        await db.commit()


# ============================================================
# 活动列表
# ============================================================

async def list_campaigns(
    store_id: str,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> CampaignListResponse:
    """活动列表（分页）"""
    # 计数
    count_result = await db.execute(
        select(func.count(Campaign.id)).where(Campaign.store_id == store_id)
    )
    total = count_result.scalar() or 0

    # 查询
    result = await db.execute(
        select(Campaign)
        .where(Campaign.store_id == store_id)
        .order_by(desc(Campaign.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    campaigns = list(result.scalars().all())

    # 组装含 log_summary 的响应
    items = []
    for campaign in campaigns:
        log_summary = await _get_log_summary(campaign.id, db)
        items.append(CampaignOut(
            id=campaign.id,
            store_id=campaign.store_id,
            name=campaign.name,
            template=campaign.template,
            channels=campaign.channels,
            scheduled_at=campaign.scheduled_at,
            status=campaign.status,
            created_by=campaign.created_by,
            created_at=campaign.created_at,
            log_summary=log_summary,
        ))

    return CampaignListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_campaign_detail(
    campaign_id: str,
    store_id: str,
    db: AsyncSession,
) -> CampaignOut:
    """活动详情"""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.store_id == store_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")

    log_summary = await _get_log_summary(campaign.id, db)

    return CampaignOut(
        id=campaign.id,
        store_id=campaign.store_id,
        name=campaign.name,
        template=campaign.template,
        channels=campaign.channels,
        scheduled_at=campaign.scheduled_at,
        status=campaign.status,
        created_by=campaign.created_by,
        created_at=campaign.created_at,
        log_summary=log_summary,
    )


async def get_campaign_logs(
    campaign_id: str,
    store_id: str,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[CampaignLogOut], int]:
    """活动发送日志（分页）"""
    # 校验归属
    camp_result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.store_id == store_id,
        )
    )
    if not camp_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="活动不存在")

    count_result = await db.execute(
        select(func.count(CampaignLog.id)).where(
            CampaignLog.campaign_id == campaign_id,
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(CampaignLog)
        .where(CampaignLog.campaign_id == campaign_id)
        .order_by(desc(CampaignLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = list(result.scalars().all())

    return [CampaignLogOut.model_validate(log) for log in logs], total


# ============================================================
# 内部工具
# ============================================================

async def _get_log_summary(campaign_id: str, db: AsyncSession) -> CampaignLogSummary:
    """获取活动的发送统计"""
    result = await db.execute(
        select(CampaignLog).where(CampaignLog.campaign_id == campaign_id)
    )
    logs = list(result.scalars().all())

    return CampaignLogSummary(
        total=len(logs),
        sent=sum(1 for l in logs if l.status == "sent"),
        failed=sum(1 for l in logs if l.status == "failed"),
        pending=sum(1 for l in logs if l.status == "pending"),
    )
