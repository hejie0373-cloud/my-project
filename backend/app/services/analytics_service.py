"""
数据分析与报表服务
"""
import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, Visit
from app.models.ai_metric import AiMetric
from app.models.campaign import CampaignLog
from app.schemas.analytics import (
    DashboardData,
    VisitTrendPoint,
    TopCustomer,
    VisitReportItem,
    RevenueReportItem,
    AiReportData,
)

logger = logging.getLogger(__name__)

CACHE_TTL_DASHBOARD = 60       # 仪表盘缓存 60 秒
CACHE_TTL_REPORT = 300         # 报表缓存 300 秒


async def _get_cache(key: str) -> Optional[dict]:
    """读 Redis 缓存"""
    try:
        from app.utils.redis_client import get_redis
        r = await get_redis()
        data = await r.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


async def _set_cache(key: str, data: dict, ttl: int) -> None:
    """写 Redis 缓存"""
    try:
        from app.utils.redis_client import get_redis
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(data, default=str, ensure_ascii=False))
    except Exception:
        pass


# ============================================================
# 仪表盘
# ============================================================

async def get_dashboard_data(store_id: str, db: AsyncSession) -> DashboardData:
    """仪表盘聚合数据（Redis 缓存 60 秒）"""
    cache_key = f"dashboard:{store_id}"
    cached = await _get_cache(cache_key)
    if cached:
        return DashboardData(**cached)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = today_start - timedelta(days=6)

    # --- 总客户数 ---
    total_result = await db.execute(
        select(func.count(Customer.id)).where(
            Customer.store_id == store_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )
    total_customers = total_result.scalar() or 0

    # --- 高风险客户数 ---
    high_risk_result = await db.execute(
        select(func.count(AiMetric.id)).where(
            AiMetric.store_id == store_id,
            AiMetric.churn_score > 60,
        )
    )
    high_risk_count = high_risk_result.scalar() or 0

    # --- 高价值客户数 (CLV > 1000) ---
    high_value_result = await db.execute(
        select(func.count(AiMetric.id)).where(
            AiMetric.store_id == store_id,
            AiMetric.clv > 1000,
        )
    )
    high_value_count = high_value_result.scalar() or 0

    # --- 今日到店数 ---
    today_visits_result = await db.execute(
        select(func.count(Visit.id)).where(
            Visit.store_id == store_id,
            Visit.visited_at >= today_start,
        )
    )
    today_visits = today_visits_result.scalar() or 0

    # --- 近 7 天到店趋势 ---
    visit_trend = []
    for i in range(6, -1, -1):
        day = (today_start - timedelta(days=i)).date()
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        count_result = await db.execute(
            select(func.count(Visit.id)).where(
                Visit.store_id == store_id,
                Visit.visited_at >= day_start,
                Visit.visited_at < day_end,
            )
        )
        visit_trend.append(VisitTrendPoint(
            date=day.isoformat(),
            count=count_result.scalar() or 0,
        ))

    # --- Top 5 高风险客户 ---
    top_result = await db.execute(
        select(Customer.id, Customer.name, Customer.phone, AiMetric.churn_score)
        .join(AiMetric, Customer.id == AiMetric.customer_id)
        .where(
            Customer.store_id == store_id,
            Customer.is_deleted == False,  # noqa: E712
            AiMetric.churn_score > 0,
        )
        .order_by(AiMetric.churn_score.desc())
        .limit(5)
    )
    top_customers = [
        TopCustomer(id=row[0], name=row[1], phone=row[2], churn_score=row[3])
        for row in top_result.all()
    ]

    # --- 流失分布 ---
    high = high_risk_count
    medium_result = await db.execute(
        select(func.count(AiMetric.id)).where(
            AiMetric.store_id == store_id,
            AiMetric.churn_score >= 30,
            AiMetric.churn_score <= 60,
        )
    )
    medium = medium_result.scalar() or 0
    low_result = await db.execute(
        select(func.count(AiMetric.id)).where(
            AiMetric.store_id == store_id,
            AiMetric.churn_score < 30,
        )
    )
    low = low_result.scalar() or 0

    data = DashboardData(
        total_customers=total_customers,
        high_risk_count=high_risk_count,
        high_value_count=high_value_count,
        today_visits=today_visits,
        visit_trend=visit_trend,
        top_risk_customers=top_customers,
        churn_distribution={"high": high, "medium": medium, "low": low},
    )

    await _set_cache(cache_key, data.model_dump(), CACHE_TTL_DASHBOARD)
    return data


# ============================================================
# 报表查询
# ============================================================

def _granularity_sql(field: str, granularity: str) -> str:
    """生成 MySQL 分组表达式"""
    if granularity == "day":
        return f"DATE({field})"
    elif granularity == "week":
        return f"YEARWEEK({field}, 1)"
    elif granularity == "month":
        return f"DATE_FORMAT({field}, '%Y-%m')"
    raise ValueError(f"Unsupported granularity: {granularity}")


async def get_visit_report(
    store_id: str,
    start_date: date,
    end_date: date,
    granularity: str,
    db: AsyncSession,
) -> List[VisitReportItem]:
    """到店报表：按粒度分组的到店量和独立客户数"""
    cache_key = f"report:{store_id}:visits:{start_date}:{end_date}:{granularity}"
    cached = await _get_cache(cache_key)
    if cached:
        return [VisitReportItem(**item) for item in cached]

    group_expr = _granularity_sql("visited_at", granularity)

    sql = text(f"""
        SELECT
            {group_expr} AS period,
            COUNT(*) AS visit_count,
            COUNT(DISTINCT customer_id) AS unique_customers
        FROM visits
        WHERE store_id = :store_id
          AND visited_at >= :start_date
          AND visited_at < :end_date2
        GROUP BY period
        ORDER BY period
    """)

    result = await db.execute(sql, {
        "store_id": store_id,
        "start_date": start_date,
        "end_date2": end_date + timedelta(days=1),
    })
    rows = result.all()

    items = [
        VisitReportItem(
            period=str(row[0]),
            visit_count=row[1],
            unique_customers=row[2],
        )
        for row in rows
    ]

    await _set_cache(cache_key, [item.model_dump() for item in items], CACHE_TTL_REPORT)
    return items


async def get_revenue_report(
    store_id: str,
    start_date: date,
    end_date: date,
    granularity: str,
    db: AsyncSession,
) -> List[RevenueReportItem]:
    """营收报表：按粒度分组的消费总额、客单价"""
    cache_key = f"report:{store_id}:revenue:{start_date}:{end_date}:{granularity}"
    cached = await _get_cache(cache_key)
    if cached:
        return [RevenueReportItem(**item) for item in cached]

    group_expr = _granularity_sql("visited_at", granularity)

    sql = text(f"""
        SELECT
            {group_expr} AS period,
            COALESCE(SUM(amount), 0) AS total_amount,
            COALESCE(AVG(amount), 0) AS avg_amount,
            COALESCE(SUM(CASE WHEN payment_method = 'wechat_pay' THEN amount ELSE 0 END), 0) AS wechat_total,
            COALESCE(SUM(CASE WHEN payment_method = 'alipay' THEN amount ELSE 0 END), 0) AS alipay_total,
            COALESCE(SUM(CASE WHEN payment_method NOT IN ('wechat_pay', 'alipay') OR payment_method IS NULL THEN amount ELSE 0 END), 0) AS other_total
        FROM visits
        WHERE store_id = :store_id
          AND visited_at >= :start_date
          AND visited_at < :end_date2
        GROUP BY period
        ORDER BY period
    """)

    result = await db.execute(sql, {
        "store_id": store_id,
        "start_date": start_date,
        "end_date2": end_date + timedelta(days=1),
    })
    rows = result.all()

    items = [
        RevenueReportItem(
            period=str(row[0]),
            total_amount=round(float(row[1]), 2),
            avg_amount=round(float(row[2]), 2),
            payment_distribution={
                "wechat_pay": round(float(row[3]), 2),
                "alipay": round(float(row[4]), 2),
                "other": round(float(row[5]), 2),
            },
        )
        for row in rows
    ]

    await _set_cache(cache_key, [item.model_dump() for item in items], CACHE_TTL_REPORT)
    return items


async def get_ai_report(
    store_id: str,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> AiReportData:
    """AI 指标报表"""
    cache_key = f"report:{store_id}:ai:{start_date}:{end_date}"
    cached = await _get_cache(cache_key)
    if cached:
        return AiReportData(**cached)

    # 高风险数
    high_risk_result = await db.execute(
        select(func.count(AiMetric.id)).where(
            AiMetric.store_id == store_id,
            AiMetric.churn_score > 60,
        )
    )
    high_risk_count = high_risk_result.scalar() or 0

    # 分数段分布
    brackets = [
        ("0-20", 0, 20),
        ("20-40", 20, 40),
        ("40-60", 40, 60),
        ("60-80", 60, 80),
        ("80-100", 80, 100),
    ]
    distribution = {}
    for label, low, high in brackets:
        count_result = await db.execute(
            select(func.count(AiMetric.id)).where(
                AiMetric.store_id == store_id,
                AiMetric.churn_score >= low,
                AiMetric.churn_score < high if high < 100 else AiMetric.churn_score <= high,
            )
        )
        distribution[label] = count_result.scalar() or 0

    # 平均 CLV
    clv_result = await db.execute(
        select(func.avg(AiMetric.clv)).where(
            AiMetric.store_id == store_id,
            AiMetric.clv > 0,
        )
    )
    clv_avg = round(float(clv_result.scalar() or 0), 2)

    # 文案采纳率（本期间）
    logs_total_result = await db.execute(
        select(func.count(CampaignLog.id)).where(
            CampaignLog.created_at >= start_date,
            CampaignLog.created_at < end_date + timedelta(days=1),
        )
    )
    logs_total = logs_total_result.scalar() or 0

    logs_sent_result = await db.execute(
        select(func.count(CampaignLog.id)).where(
            CampaignLog.created_at >= start_date,
            CampaignLog.created_at < end_date + timedelta(days=1),
            CampaignLog.status == "sent",
        )
    )
    logs_sent = logs_sent_result.scalar() or 0

    copy_adoption_rate = round(logs_sent / logs_total * 100, 1) if logs_total > 0 else 0.0

    # 已评分客户数
    scored_result = await db.execute(
        select(func.count(AiMetric.id)).where(
            AiMetric.store_id == store_id,
        )
    )
    total_scored = scored_result.scalar() or 0

    data = AiReportData(
        high_risk_count=high_risk_count,
        churn_score_distribution=distribution,
        clv_avg=clv_avg,
        copy_adoption_rate=copy_adoption_rate,
        total_customers_scored=total_scored,
    )

    await _set_cache(cache_key, data.model_dump(), CACHE_TTL_REPORT)
    return data
