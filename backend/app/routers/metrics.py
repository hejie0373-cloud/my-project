"""
AI 指标路由：流失评分、CLV、文案生成
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_quota
from app.db.session import get_db
from app.models.user import User
from app.models.ai_metric import AiMetric
from app.schemas.ai_metric import (
    ChurnScoreResponse,
    ClvResponse,
    CopyResponse,
    GenerateCopyRequest,
    BatchScoreTaskResponse,
)
from app.services.ai_service import (
    calculate_churn_score,
    calculate_clv,
    generate_followup_copy,
)
from sqlalchemy import desc, select
from app.models.customer import Customer, Visit

router = APIRouter()


@router.post("/churn/batch", response_model=BatchScoreTaskResponse, summary="批量评分（异步）")
async def trigger_batch_score(
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
):
    """
    触发当前店铺全量评分（Celery 异步任务）

    返回 task_id 用于追踪
    """
    from app.tasks.scoring_task import batch_score_all_customers
    task = batch_score_all_customers.delay(store_id=store_id)

    return BatchScoreTaskResponse(
        task_id=task.id,
        message="批量评分任务已提交",
        scope=f"store:{store_id}",
    )


@router.post("/churn/{customer_id}", response_model=ChurnScoreResponse, summary="触发客户流失评分")
async def trigger_churn_score(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
    db: AsyncSession = Depends(get_db),
):
    """
    计算单个客户的流失风险评分（同步）

    评分维度：
    - 到店间隔 (40%)
    - 到店频率 (30%)
    - 消费趋势 (30%)

    结果写入 ai_metrics 表，高风险自动发布预警
    """
    result = await calculate_churn_score(customer_id, db)
    return result


@router.get("/churn/{customer_id}", response_model=ChurnScoreResponse, summary="查询已计算评分")
async def get_churn_score(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
    db: AsyncSession = Depends(get_db),
):
    """
    读取客户最近一次计算的评分结果

    如未计算过，自动触发计算
    """
    result = await db.execute(
        select(AiMetric).where(AiMetric.customer_id == customer_id)
    )
    metric = result.scalar_one_or_none()

    if metric and metric.churn_score is not None and metric.computed_at:
        from app.schemas.ai_metric import ChurnScoreResponse
        return ChurnScoreResponse(
            customer_id=customer_id,
            churn_score=metric.churn_score,
            clv=metric.clv or 0,
            recommendation=metric.recommendation or "",
            dimensions={},
            computed_at=metric.computed_at,
        )

    # 无缓存 → 触发计算
    return await calculate_churn_score(customer_id, db)


@router.get("/lifetime-value/{customer_id}", response_model=ClvResponse, summary="查询 CLV")
async def get_clv(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
    db: AsyncSession = Depends(get_db),
):
    """
    读取客户终身价值估算
    """
    return await calculate_clv(customer_id, db)


@router.post("/copy", response_model=CopyResponse, summary="AI 生成跟进文案")
async def generate_copy(
    data: GenerateCopyRequest,
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
    db: AsyncSession = Depends(get_db),
):
    """
    生成跟进文案（Dify → DeepSeek → 本地模板三级 fallback）

    - sms: 70 字以内短信
    - email: 150-300 字正式邮件
    - wechat: 50-150 字口语化消息
    - 高风险客户 (churn>80) 标记 require_confirmation=true
    """
    return await generate_followup_copy(
        customer_id=data.customer_id,
        channel=data.channel,
        db=db,
    )


@router.post("/predict/batch", summary="Dify 批量流失预测")
async def batch_predict(
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
    db: AsyncSession = Depends(get_db),
):
    """
    Dify 批量流失预测

    对当前店铺所有有到店记录的客户调用 Dify 工作流评分
    需要配置 DIFY_CHURN_API_KEY 环境变量
    """
    from app.services import dify_service
    from app.core.config import settings
    from app.models.store import Store

    if not settings.DIFY_CHURN_API_KEY:
        raise HTTPException(400, "请先配置 DIFY_CHURN_API_KEY")

    # 查店铺信息
    store_result = await db.execute(select(Store).where(Store.id == store_id))
    store = store_result.scalar_one_or_none()

    # 查所有客户及到店记录
    customers_result = await db.execute(
        select(Customer).where(
            Customer.store_id == store_id,
            Customer.is_deleted == False,  # noqa: E712
        )
    )
    customers = customers_result.scalars().all()

    batch_data = []
    for cust in customers:
        visits_result = await db.execute(
            select(Visit)
            .where(Visit.customer_id == cust.id)
            .order_by(desc(Visit.visited_at))
            .limit(10)
        )
        visits = visits_result.scalars().all()
        batch_data.append({
            "id": cust.id,
            "name": cust.name,
            "visits": [
                {"date": str(v.visited_at), "service": v.service_type, "amount": float(v.amount)}
                for v in visits
            ],
        })

    results = await dify_service.batch_predict(
        customers=batch_data,
        store_name=store.name if store else "",
        store_industry=store.industry_type if store else "",
        api_key=settings.DIFY_CHURN_API_KEY,
    )

    return {"total": len(results), "results": results}


@router.post("/insight", summary="Dify AI 客户洞察")
async def ai_insight(
    question: str = Query(..., description="自然语言问题，如「哪些客户最可能流失」"),
    current_user: User = Depends(get_current_user),
    store_id: str = require_quota("ai"),
    db: AsyncSession = Depends(get_db),
):
    """
    Dify AI 对话洞察

    自动搜索问题中提到的客户，将数据作为上下文提供给 AI
    """
    from app.services import dify_service
    from app.core.config import settings
    from app.models.store import Store
    from app.models.customer import Customer
    from app.models.ai_metric import AiMetric
    import re

    if not settings.DIFY_INSIGHT_API_KEY:
        raise HTTPException(400, "请先配置 DIFY_INSIGHT_API_KEY")

    store_result = await db.execute(select(Store).where(Store.id == store_id))
    store = store_result.scalar_one_or_none()

    # 搜索问题中提到的客户（滑动窗口 2-3 字中文片段）
    customer_context = ""
    names_found = set()
    # 提取所有连续中文片段
    chinese_chars = re.findall(r"[一-鿿]+", question)
    searched = set()
    for chunk in chinese_chars:
        # 滑动窗口：2字和3字
        for wlen in (2, 3):
            for i in range(len(chunk) - wlen + 1):
                name = chunk[i:i+wlen]
                if name in searched:
                    continue
                searched.add(name)
                cust_result = await db.execute(
                    select(Customer).where(
                        Customer.store_id == store_id,
                        Customer.name.like(f"%{name}%"),
                        Customer.is_deleted == False,  # noqa
                    ).limit(3)
                )
                for c in cust_result.scalars().all():
                    if c.name not in names_found:
                        names_found.add(c.name)
                        ai = (await db.execute(
                            select(AiMetric).where(AiMetric.customer_id == c.id)
                        )).scalar_one_or_none()
                        churn = f"流失{ai.churn_score}分" if ai and ai.churn_score else "未评分"
                        clv = f"年价值¥{ai.clv:,.0f}" if ai and ai.clv else ""
                        customer_context += f"- {c.name}({c.phone}): {churn}, {clv}\n"

    # 构造增强提问
    enhanced_question = question
    if customer_context:
        enhanced_question = (
            f"用户提问：{question}\n\n"
            f"以下是从店铺数据库中查到的真实客户数据，请基于这些具体数据回答：\n{customer_context}"
        )
    elif searched:
        enhanced_question = (
            f"用户提问：{question}\n\n"
            f"（系统已搜索店铺数据库，未找到匹配的客户。请如实告知用户未找到，不要假装能看到数据。）"
        )
        logger.info(f"[AI Insight] 找到 {len(names_found)} 个匹配客户，上下文长度: {len(customer_context)}")
    else:
        logger.info(f"[AI Insight] 未找到匹配客户，问题: {question[:50]}")

    answer = await dify_service.chat_insight(
        question=enhanced_question,
        store_name=store.name if store else "",
        store_industry=store.industry_type if store else "",
    )

    if not answer:
        raise HTTPException(500, "Dify 调用失败，请检查 API Key 配置")

    return {"question": question, "answer": answer, "source": "dify"}
