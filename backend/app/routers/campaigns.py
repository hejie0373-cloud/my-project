"""
营销活动路由
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_quota, require_store
from app.db.session import get_db
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignOut,
    CampaignListResponse,
    CampaignLogOut,
)
from app.services.campaign_service import (
    create_campaign,
    list_campaigns,
    get_campaign_detail,
    get_campaign_logs,
)

router = APIRouter()


@router.post("", response_model=CampaignOut, status_code=201, summary="创建营销活动")
async def create_campaign_endpoint(
    data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("campaign"),
    db: AsyncSession = Depends(get_db),
):
    """
    创建并发送营销活动

    - 支持选择目标客户（指定 ID 或按风险筛选）
    - 支持多渠道（短信/邮件/微信）
    - 未指定 scheduled_at 则立即发送
    - 模板支持 {{客户姓名}} {{服务项目}} {{推荐到店日期}} {{店铺名称}} 变量
    """
    campaign = await create_campaign(
        store_id=store_id,
        created_by=current_user.id,
        data=data,
        db=db,
    )
    return await get_campaign_detail(campaign.id, store_id, db)


@router.get("", response_model=CampaignListResponse, summary="活动列表")
async def list_campaigns_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """活动列表（分页，含发送统计）"""
    return await list_campaigns(store_id=store_id, db=db, page=page, page_size=page_size)


@router.get("/{campaign_id}", response_model=CampaignOut, summary="活动详情")
async def get_campaign_endpoint(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """活动详情（含发送日志统计）"""
    return await get_campaign_detail(campaign_id, store_id, db)


@router.get("/{campaign_id}/logs", response_model=dict, summary="发送日志")
async def get_logs_endpoint(
    campaign_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """活动发送日志（分页）"""
    logs, total = await get_campaign_logs(
        campaign_id=campaign_id,
        store_id=store_id,
        db=db,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [log.model_dump() for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
