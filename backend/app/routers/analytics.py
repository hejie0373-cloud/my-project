"""
数据分析与报表路由
"""
import csv
import io
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_quota, require_store
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import DashboardData
from app.services.analytics_service import (
    get_dashboard_data,
    get_visit_report,
    get_revenue_report,
    get_ai_report,
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardData, summary="仪表盘数据")
async def dashboard(
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """
    仪表盘聚合数据（Redis 缓存 60 秒）

    返回:
    - 总客户数 / 高风险数 / 高价值数 / 今日到店
    - 近 7 天到店趋势
    - Top 5 高风险客户
    - 流失分布
    """
    return await get_dashboard_data(store_id, db)


@router.get("/reports", summary="报表查询")
async def reports(
    type: Literal["visits", "revenue", "ai"] = Query(..., description="报表类型"),
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
    granularity: Literal["day", "week", "month"] = Query("day", description="粒度"),
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """
    报表查询（到店/营收/AI指标）

    - visits: 到店量 + 独立客户数
    - revenue: 消费总额 + 客单价 + 支付方式分布
    - ai: 风险分布 + 平均CLV + 文案采纳率
    - granularity: day/week/month
    - 结果 Redis 缓存 300 秒
    """
    if type == "visits":
        return await get_visit_report(store_id, start_date, end_date, granularity, db)
    elif type == "revenue":
        return await get_revenue_report(store_id, start_date, end_date, granularity, db)
    elif type == "ai":
        return await get_ai_report(store_id, start_date, end_date, db)


@router.get("/export", summary="CSV 流式导出")
async def export_csv(
    type: Literal["customers", "visits"] = Query(..., description="导出类型"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("export"),
    db: AsyncSession = Depends(get_db),
):
    """
    CSV 流式导出（最大 50,000 行）

    - customers: 导出客户列表（含评分）
    - visits: 导出到店记录
    """
    from datetime import timedelta

    async def generate():
        """CSV 生成器（逐行 yield，不撑爆内存）"""
        output = io.StringIO()
        writer = csv.writer(output)

        if type == "customers":
            from app.models.customer import Customer
            from app.models.ai_metric import AiMetric
            from sqlalchemy import select

            writer.writerow([
                "ID", "姓名", "手机号", "性别", "生日", "地址",
                "流失评分", "CLV", "最近评分时间", "创建时间",
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            query = (
                select(
                    Customer.id, Customer.name, Customer.phone,
                    Customer.gender, Customer.birthday, Customer.address,
                    AiMetric.churn_score, AiMetric.clv, AiMetric.computed_at,
                    Customer.created_at,
                )
                .outerjoin(AiMetric, Customer.id == AiMetric.customer_id)
                .where(
                    Customer.store_id == store_id,
                    Customer.is_deleted == False,  # noqa: E712
                )
                .limit(50000)
            )

            result = await db.execute(query)
            for row in result.all():
                writer.writerow([
                    row[0], row[1], row[2], row[3],
                    str(row[4]) if row[4] else "",
                    row[5] or "",
                    row[6] if row[6] is not None else "",
                    row[7] if row[7] is not None else "",
                    str(row[8]) if row[8] else "",
                    str(row[9]),
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        elif type == "visits":
            from app.models.customer import Visit
            from sqlalchemy import select

            writer.writerow([
                "ID", "客户ID", "到店时间", "服务类型", "员工",
                "消费金额", "支付方式", "反馈", "来源",
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            query = (
                select(Visit)
                .where(Visit.store_id == store_id)
                .order_by(Visit.visited_at.desc())
                .limit(50000)
            )

            if start_date:
                query = query.where(Visit.visited_at >= start_date)
            if end_date:
                query = query.where(Visit.visited_at < end_date + timedelta(days=1))

            result = await db.execute(query)
            for visit in result.scalars().all():
                writer.writerow([
                    visit.id, visit.customer_id,
                    str(visit.visited_at), visit.service_type,
                    visit.staff_name or "", float(visit.amount),
                    visit.payment_method or "", visit.feedback or "",
                    visit.source,
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

    filename = f"export_{type}_{date.today().isoformat()}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
