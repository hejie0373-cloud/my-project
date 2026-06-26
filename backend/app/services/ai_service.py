"""
AI 智能引擎：流失评分、CLV 估算、推荐行动、文案生成

评分算法：三维度加权
  - 到店间隔（40%）：距上次到店天数 / 90 天规范化为 0-100
  - 到店频率（30%）：月均到店次数 vs 基准频率
  - 消费趋势（30%）：近 3 次消费 vs 前 3 次消费
"""
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.customer import Customer, Visit
from app.models.ai_metric import AiMetric
from app.models.store import Store
from app.schemas.ai_metric import (
    ChurnScoreResponse,
    ClvResponse,
    CopyResponse,
)
from app.services import dify_service

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 到店间隔评分阶梯（天数, 分数）
RECENCY_BRACKETS = [
    (float("inf"), 100),  # 更久
    (90, 90),     # 三个月
    (60, 75),     # 两个月
    (30, 55),     # 一个月
    (14, 30),     # 两周
    (7, 15),      # 一周内
    (0, 0),       # 今天到店
]

# 月均到店频率评分阶梯（次/月, 分数）
FREQUENCY_BRACKETS = [
    (float("inf"), 0),   # 非常高（好）
    (4, 15),              # >=4次/月
    (2, 35),              # 2-3次/月
    (1, 55),              # 1-2次/月
    (0.3, 80),            # <1次/月
    (0, 100),             # 无记录
]

# 消费趋势评分阶梯（变化率 % , 分数）
TREND_BRACKETS = [
    (float("inf"), 0),    # 大幅上升（好）
    (10, 15),             # 上升 >10%
    (-10, 35),            # 持平 ±10%
    (-30, 65),            # 下降 >10%
    (float("-inf"), 90),  # 大幅下降
]


def _score_from_brackets(value: float, brackets: List[Tuple[float, float]]) -> float:
    """
    根据阶梯表打分
    brackets: [(threshold, score), ...] 从小到大排列，第一个匹配的为准
    """
    for threshold, score in brackets:
        if value >= threshold:
            return score
    return 0.0


# ============================================================
# 流失风险评分
# ============================================================

async def _get_visit_stats(
    customer_id: str, db: AsyncSession
) -> Tuple[List[Visit], int, Optional[datetime], float, int]:
    """
    获取客户的到店统计数据

    返回: (all_visits, total_count, last_visited_at, monthly_freq, active_months)
    """
    # 所有到店记录（按时间倒序）
    result = await db.execute(
        select(Visit)
        .where(Visit.customer_id == customer_id)
        .order_by(desc(Visit.visited_at))
    )
    visits = list(result.scalars().all())

    total = len(visits)

    if total == 0:
        return [], 0, None, 0.0, 0

    last_visited = visits[0].visited_at
    first_visited = visits[-1].visited_at

    # 活跃月数
    days_span = (datetime.utcnow() - first_visited).days
    active_months = max(1, days_span // 30)

    # 月均到店次数
    monthly_freq = total / active_months

    return visits, total, last_visited, monthly_freq, active_months


async def calculate_churn_score(
    customer_id: str, db: AsyncSession
) -> ChurnScoreResponse:
    """
    计算客户流失风险评分（Dify AI 优先 → 规则引擎兜底）
    相同客户 1 小时内不重复调用 Dify
    """
    # 缓存：1 小时内算过直接返回
    from app.utils.cache import get as cache_get, set as cache_set, TTL_LONG
    cache_key = f"churn:{customer_id}"
    cached = await cache_get(cache_key)
    if cached:
        logger.info(f"评分缓存命中: customer={customer_id}")
        return ChurnScoreResponse(**cached)

    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    visits, total, last_visited, monthly_freq, active_months = await _get_visit_stats(
        customer_id, db
    )

    now = datetime.utcnow()

    # ---- 维度 1: 到店间隔 (recency) ----
    if last_visited:
        days_since = (now - last_visited).days
    else:
        days_since = 999

    # ---- 尝试 Dify AI 预测 ----
    dify_score = None
    dify_clv = None
    dify_report = ""
    if settings.DIFY_CHURN_API_KEY:
        try:
            store_result = await db.execute(select(Store).where(Store.id == customer.store_id))
            store = store_result.scalar_one_or_none()
            total_spent = sum(float(v.amount) for v in visits)
            visits_json = str([
                {"date": str(v.visited_at), "service": v.service_type, "amount": float(v.amount)}
                for v in visits[:20]
            ])
            dify_result = await dify_service.predict_churn(
                customer_name=customer.name,
                store_name=store.name if store else "店铺",
                visit_history=visits_json,
                total_spent=total_spent,
                days_ago=days_since,
                visit_count=total,
            )
            if dify_result:
                data_block = dify_result.get("data", {})
                outputs = data_block.get("outputs", {})
                dify_score = float(outputs.get("risk_score", 0))
                dify_clv = float(outputs.get("annual_value", 0))
                dify_report = outputs.get("report", "") or data_block.get("text", "") or outputs.get("text", "")
                # 清除 DeepSeek 的 <think> 标签
                dify_report = re.sub(r'<think>[\s\S]*?</think>', '', dify_report).strip()
                logger.info(f"Dify AI: customer={customer_id}, score={dify_score}, report_len={len(dify_report)}")
        except Exception as e:
            logger.warning(f"Dify 预测失败，回退规则引擎: {e}")

    # ---- Dify 成功 → 直接用 AI 评分 ----
    if dify_score is not None:
        churn_score = min(max(dify_score, 0), 100)
        recency_score = frequency_score = trend_score = 0  # AI 不分解维度
    else:
        # ---- 规则引擎兜底 ----
        recency_score = _score_from_brackets(days_since, RECENCY_BRACKETS)

        if total < 2:
            frequency_score = 70
        else:
            frequency_score = _score_from_brackets(monthly_freq, FREQUENCY_BRACKETS)

        if total < 3:
            trend_score = 40
        else:
            recent_3 = visits[:3]
            earlier_3 = visits[3:6] if total >= 6 else visits[3:]
            recent_avg = sum(float(v.amount) for v in recent_3) / len(recent_3)
            earlier_avg = sum(float(v.amount) for v in earlier_3) / len(earlier_3) if earlier_3 else recent_avg
            change_pct = ((recent_avg - earlier_avg) / earlier_avg) * 100 if earlier_avg > 0 else 0
            trend_score = _score_from_brackets(change_pct, TREND_BRACKETS)

        churn_score = round(recency_score * 0.4 + frequency_score * 0.3 + trend_score * 0.3, 1)
        churn_score = min(max(churn_score, 0), 100)

    # ---- 计算 CLV（Dify 优先） ----
    if dify_clv is not None:
        clv = dify_clv
    else:
        clv = await _calculate_clv_internal(customer_id, visits, total, active_months, churn_score)

    # ---- 生成推荐（Dify 优先） ----
    recommendation = dify_report if dify_report else _generate_recommendation(churn_score, days_since, customer.name)

    # ---- 写入/更新 ai_metrics ----
    await _upsert_ai_metric(
        db=db,
        customer_id=customer_id,
        store_id=customer.store_id,
        churn_score=churn_score,
        clv=clv,
        recommendation=recommendation,
    )

    # 高风险预警
    if churn_score > 60:
        await _send_high_risk_alert(customer_id, customer.store_id, churn_score, db)

    dimensions = {
        "recency_score": recency_score,
        "recency_weight": 0.4,
        "days_ago": days_since,
        "frequency_score": frequency_score,
        "frequency_weight": 0.3,
        "monthly_visits": round(monthly_freq, 2),
        "trend_score": trend_score,
        "trend_weight": 0.3,
        "total_visits": total,
    }

    logger.info(
        f"评分完成: customer={customer_id}, "
        f"churn={churn_score}, recency={recency_score}, "
        f"freq={frequency_score}, trend={trend_score}"
    )

    response = ChurnScoreResponse(
        customer_id=customer_id,
        churn_score=churn_score,
        clv=clv,
        recommendation=recommendation,
        dimensions=dimensions,
        computed_at=datetime.utcnow(),
    )
    await cache_set(cache_key, response.model_dump(), TTL_LONG)
    # 清除客户详情缓存，确保前端拉取到最新评分
    from app.utils.cache import delete as cache_delete
    await cache_delete(f"customer_detail:{customer_id}")
    return response


# ============================================================
# CLV 估算
# ============================================================

async def _calculate_clv_internal(
    customer_id: str,
    visits: List[Visit],
    total: int,
    active_months: int,
    churn_score: float,
) -> float:
    """
    计算 CLV（客户终身价值）

    公式: CLV = 月均消费 × 预估剩余生命周期
    - 月均消费 = 总消费 / 活跃月数
    - 预估剩余生命周期 = (100 - churn_score) / 100 × 24（月）
    """
    if total == 0:
        return 0.0

    total_spend = sum(float(v.amount) for v in visits)
    avg_monthly_spend = total_spend / active_months

    # 预估留存月数：流失分越低，留存越久
    retention_months = max(1, (100 - churn_score) / 100 * 24)

    clv = round(avg_monthly_spend * retention_months, 2)
    return clv


async def calculate_clv(customer_id: str, db: AsyncSession) -> ClvResponse:
    """获取 CLV 估算（对外接口）"""
    visits, total, last_visited, monthly_freq, active_months = await _get_visit_stats(
        customer_id, db
    )

    # 先读已有的 churn_score，没有则用默认值
    result = await db.execute(
        select(AiMetric).where(AiMetric.customer_id == customer_id)
    )
    metric = result.scalar_one_or_none()
    churn_score = metric.churn_score if metric else 50

    clv = await _calculate_clv_internal(
        customer_id, visits, total, active_months, churn_score
    )

    total_spend = sum(float(v.amount) for v in visits)
    avg_monthly_spend = total_spend / active_months if active_months > 0 else 0
    retention_months = max(1, (100 - churn_score) / 100 * 24)

    data_sufficiency = "sufficient" if total >= 2 else "insufficient"

    return ClvResponse(
        customer_id=customer_id,
        clv=clv,
        avg_monthly_spend=round(avg_monthly_spend, 2),
        retention_months=round(retention_months, 1),
        data_sufficiency=data_sufficiency,
    )


# ============================================================
# 推荐行动（规则引擎）
# ============================================================

def _generate_recommendation(
    churn_score: float, days_since: float, customer_name: str
) -> str:
    """
    基于规则的推荐行动生成

    - 不调 LLM → 零 Token 消耗
    - 覆盖 80% 常见场景
    """
    if churn_score > 60:
        if days_since > 90:
            return (
                f"🔴 极高流失风险：{customer_name}已超过 3 个月未到店。"
                "建议立即电话回访并赠送「回归礼遇」优惠券，优惠力度建议 ≥ 7 折"
            )
        return (
            f"⚠️ 高流失风险：{customer_name}已有 {int(days_since)} 天未到店。"
            "建议本周内发送专属优惠，并附个性化问候，优惠力度建议 ≥ 8 折"
        )
    elif churn_score >= 30:
        return (
            f"🟡 中等风险：距上次到店已 {int(days_since)} 天。"
            "建议本周四/周五发送温馨提醒，可搭配季节性服务推荐"
        )
    else:
        if days_since < 7:
            return (
                f"🟢 忠实客户：{customer_name}最近活跃。"
                "建议在生日或节日前发送专属问候，鼓励老带新"
            )
        return (
            f"🟢 低风险：建议保持常规联系频率，"
            "关注客户生日和纪念日发送祝福"
        )


# ============================================================
# AI 文案生成（Dify → DeepSeek → Local Fallback）
# ============================================================

def _build_copy_prompt(
    customer_name: str,
    store_name: str,
    industry: str,
    service_type: str,
    days_since: int,
    churn_score: float,
    channel: str,
) -> str:
    """构建文案生成的 Prompt"""
    risk_label = "高流失风险" if churn_score > 60 else ("需关注" if churn_score > 30 else "活跃客户")

    if channel == "sms":
        return (
            f"你是{store_name}（{industry}）的客户经理。"
            f"客户{customer_name}最近一次体验了「{service_type}」，距今{days_since}天。"
            f"客户风险等级：{risk_label}。"
            f"请生成一条 70 字以内的短信文案，语气亲切自然，包含到店邀请和联系方式。"
            f"只输出文案内容，不要任何解释。"
        )
    elif channel == "email":
        return (
            f"你是{store_name}（{industry}）的客户经理。"
            f"客户{customer_name}最近一次体验了「{service_type}」，距今{days_since}天。"
            f"客户风险等级：{risk_label}。"
            f"请生成一封正式邮件，包含：问候语、关怀内容、专属优惠建议、CTA 按钮文案。"
            f"语气温暖专业，篇幅 150-300 字。只输出邮件正文，不要主题行和称呼。"
        )
    else:  # wechat
        return (
            f"你是{store_name}（{industry}）的客户经理。"
            f"客户{customer_name}最近一次体验了「{service_type}」，距今{days_since}天。"
            f"客户风险等级：{risk_label}。"
            f"请生成一条微信消息，语气亲切口语化，适当使用 emoji，包含关怀和到店邀请。"
            f"篇幅 50-150 字。只输出消息内容。"
        )


def _local_template_fallback(
    customer_name: str,
    store_name: str,
    service_type: str,
    days_since: int,
    channel: str,
) -> str:
    """本地模板库（LLM 完全不可用时的兜底）"""
    templates = {
        "sms": (
            f"{customer_name}您好，{store_name}温馨提醒："
            f"您上次体验的{service_type}已过去{days_since}天了～"
            f"回复1预约到店享专属优惠，期待为您服务！"
        ),
        "email": (
            f"亲爱的{customer_name}：\n\n"
            f"距您上次光临{store_name}已有{days_since}天，我们非常想念您！\n\n"
            f"您上次体验的「{service_type}」感觉如何？为了感谢您的支持，"
            f"我们为您准备了一份专属回归好礼。\n\n"
            f"点击下方预约您的专属服务时间 👇\n"
            f"[立即预约]\n\n"
            f"期待再次为您服务！\n{store_name} 团队"
        ),
        "wechat": (
            f"Hi {customer_name}～好久不见！👋\n"
            f"距上次来{store_name}做{service_type}已经{days_since}天啦～\n"
            f"最近有专属优惠哦，快来约个时间吧 💫\n"
            f"回复「预约」即可～"
        ),
    }
    return templates.get(channel, templates["sms"])


async def _call_dify_api(prompt: str, channel: str) -> Optional[str]:
    """调用 Dify Chat API"""
    if not settings.DIFY_API_URL:
        return None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.DIFY_API_URL}/chat-messages",
                json={
                    "query": prompt,
                    "response_mode": "blocking",
                    "user": f"keliu-{channel}",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("answer")
            logger.warning(f"Dify API 返回 {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Dify API 调用失败: {e}")
        return None


async def _call_deepseek_api(prompt: str) -> Optional[str]:
    """调用 DeepSeek Chat API"""
    if not settings.DEEPSEEK_API_KEY:
        return None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是一个专业、亲切的客户经理，负责生成客户跟进文案。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.8,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0]["message"]["content"]
            logger.warning(f"DeepSeek API 返回 {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"DeepSeek API 调用失败: {e}")
        return None


async def generate_followup_copy(
    customer_id: str, channel: str, db: AsyncSession
) -> CopyResponse:
    """
    AI 文案生成（三级 fallback）

    1. Dify API →
    2. DeepSeek API →
    3. 本地模板库（保证 100% 可用）
    """
    # 查客户信息
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 查店铺信息
    store_result = await db.execute(
        select(Store).where(Store.id == customer.store_id)
    )
    store = store_result.scalar_one_or_none()
    store_name = store.name if store else "我们的店"
    industry = store.industry_type if store else "服务业"

    # 查最近服务
    visits_result = await db.execute(
        select(Visit)
        .where(Visit.customer_id == customer_id)
        .order_by(desc(Visit.visited_at))
        .limit(1)
    )
    last_visit = visits_result.scalar_one_or_none()
    service_type = last_visit.service_type if last_visit else "未记录服务"
    last_visited_at = last_visit.visited_at if last_visit else None
    days_since = (datetime.utcnow() - last_visited_at).days if last_visited_at else 999

    # 查流失分
    metric_result = await db.execute(
        select(AiMetric).where(AiMetric.customer_id == customer_id)
    )
    metric = metric_result.scalar_one_or_none()
    churn_score = metric.churn_score if metric else 50

    # 构建 Prompt
    prompt = _build_copy_prompt(
        customer_name=customer.name,
        store_name=store_name,
        industry=industry,
        service_type=service_type,
        days_since=days_since,
        churn_score=churn_score,
        channel=channel,
    )

    copy = None
    source = "local"

    # 1. 优先 Dify 工作流
    if settings.DIFY_COPY_API_KEY:
        # 计算 lifetime_value
        all_visits_result = await db.execute(
            select(func.sum(Visit.amount)).where(Visit.customer_id == customer_id)
        )
        lifetime_val = float(all_visits_result.scalar() or 0)

        channel_cn = {"sms":"短信","wechat":"微信","email":"email"}.get(channel, channel)
        copy = await dify_service.generate_copy(
            store_name=store_name,
            customer_name=customer.name,
            gender="男" if customer.gender == "male" else ("女" if customer.gender == "female" else "男"),
            last_service=service_type,
            days_ago=days_since,
            total_spent=lifetime_val,
            channel=channel_cn,
            purpose="召回" if churn_score > 60 else ("促销" if churn_score > 30 else "感谢"),
        )
        if copy:
            source = "dify"
            copy = re.sub(r'<think>[\s\S]*?</think>', '', copy).strip()
            logger.info(f"Dify 文案: customer={customer_id}, channel={channel}")

    # 2. Fallback: DeepSeek
    if not copy:
        copy = await _call_deepseek_api(prompt)
        if copy:
            source = "deepseek"
            logger.info(f"DeepSeek 生成文案: customer={customer_id}, channel={channel}")

    # 3. 最终 Fallback: 本地模板
    if not copy:
        copy = _local_template_fallback(
            customer_name=customer.name,
            store_name=store_name,
            service_type=service_type,
            days_since=days_since,
            channel=channel,
        )
        source = "local"
        logger.info(f"本地模板兜底: customer={customer_id}, channel={channel}")

    # 高风险标记
    require_confirmation = churn_score > 80

    return CopyResponse(
        customer_id=customer_id,
        channel=channel,
        content=copy,
        require_confirmation=require_confirmation,
        source=source,
    )


# ============================================================
# 内部工具函数
# ============================================================

async def _upsert_ai_metric(
    db: AsyncSession,
    customer_id: str,
    store_id: str,
    churn_score: float,
    clv: float,
    recommendation: str,
) -> AiMetric:
    """写入或更新 ai_metrics（upsert by customer_id）"""
    result = await db.execute(
        select(AiMetric).where(AiMetric.customer_id == customer_id)
    )
    metric = result.scalar_one_or_none()

    if metric:
        metric.churn_score = churn_score
        metric.clv = clv
        metric.recommendation = recommendation
        metric.computed_at = datetime.utcnow()
        # 不覆盖 alert_sent 状态
    else:
        metric = AiMetric(
            customer_id=customer_id,
            store_id=store_id,
            churn_score=churn_score,
            clv=clv,
            recommendation=recommendation,
            computed_at=datetime.utcnow(),
        )
        db.add(metric)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(AiMetric).where(AiMetric.customer_id == customer_id)
        )
        metric = result.scalar_one()
        metric.churn_score = churn_score
        metric.clv = clv
        metric.recommendation = recommendation
        metric.computed_at = datetime.utcnow()
        await db.commit()

    await db.refresh(metric)
    return metric


async def _send_high_risk_alert(
    customer_id: str, store_id: str, churn_score: float, db: AsyncSession
) -> None:
    """
    高风险预警：向 Redis Pub/Sub 发布消息

    WebSocket 实时推送用，同一客户 7 天内不重复预警
    """
    # 检查是否已发送过预警
    result = await db.execute(
        select(AiMetric).where(AiMetric.customer_id == customer_id)
    )
    metric = result.scalar_one_or_none()

    if metric and metric.alert_sent:
        # 检查距离上次预警是否超过 7 天
        if metric.computed_at:
            days_since_alert = (datetime.utcnow() - metric.computed_at).days
            if days_since_alert < 7:
                return  # 7 天内不重复预警

    try:
        from app.utils.redis_client import publish
        await publish(
            f"notify:{store_id}",
            {
                "type": "high_risk_alert",
                "customer_id": customer_id,
                "churn_score": churn_score,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"高风险预警已发布: customer={customer_id}, score={churn_score}")

        # 标记已发送
        if metric:
            metric.alert_sent = True
            await db.commit()
    except Exception as e:
        logger.warning(f"预警发布失败（Redis 可能未启动）: {e}")
