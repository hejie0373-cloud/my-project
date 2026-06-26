"""
Dify 工作流服务 — AI 引擎核心
变量名与 Dify 工作流 Start 节点严格对齐
"""
import logging
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DIFY_API = (settings.DIFY_API_URL or "http://localhost").rstrip("/")


async def _call_workflow(payload: dict, api_key: str) -> Optional[dict]:
    """通用 Dify Workflow API 调用"""
    if not api_key:
        logger.warning("Dify API key not configured")
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{DIFY_API}/v1/workflows/run",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Dify {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Dify call failed: {e}")
        return None


async def predict_churn(
    customer_name: str,
    store_name: str,
    visit_history: str,
    total_spent: float,
    days_ago: int,
    visit_count: int = 1,
) -> Optional[dict]:
    """
    流失预测工作流
    Dify Start 变量: store_name, customer_name, total_spent, visit_count, days_ago, visit_history
    输出: {report, risk_score, risk_level, annual_value}
    """
    return await _call_workflow({
        "inputs": {
            "store_name": store_name,
            "customer_name": customer_name,
            "total_spent": total_spent,
            "visit_count": visit_count,
            "days_ago": days_ago,
            "visit_history": visit_history,
        },
        "response_mode": "blocking",
        "user": customer_name,
    }, settings.DIFY_CHURN_API_KEY)


async def generate_copy(
    store_name: str,
    customer_name: str,
    gender: str,
    last_service: str,
    days_ago: int,
    total_spent: float,
    channel: str,
    purpose: str = "reactivation",
) -> Optional[str]:
    """
    营销文案生成工作流
    Dify Start 变量: store_name, customer_name, gender, last_service, days_ago, total_spent, channel, purpose
    输出: {copy_text}
    """
    result = await _call_workflow({
        "inputs": {
            "store_name": store_name,
            "customer_name": customer_name,
            "gender": gender,
            "last_service": last_service,
            "days_ago": days_ago,
            "total_spent": total_spent,
            "channel": channel,
            "purpose": purpose,
        },
        "response_mode": "blocking",
        "user": customer_name,
    }, settings.DIFY_COPY_API_KEY)
    if result:
        outputs = result.get("data", {}).get("outputs", {})
        return outputs.get("copy_text") or outputs.get("text")
    return None


async def chat_insight(
    question: str,
    store_name: str = "",
    store_industry: str = "",
) -> Optional[str]:
    """
    业务洞察对话机器人
    你的 Dify 是 advanced-chat 模式，走 chat-messages API
    输出: AI 回答文本
    """
    if not settings.DIFY_INSIGHT_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{DIFY_API}/v1/chat-messages",
                json={
                    "inputs": {
                        "store_name": store_name,
                        "store_industry": store_industry,
                    },
                    "query": question,
                    "response_mode": "blocking",
                    "user": f"store-{store_name}",
                },
                headers={"Authorization": f"Bearer {settings.DIFY_INSIGHT_API_KEY}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer") or ""
                # 清除 DeepSeek <think> 标签
                import re
                answer = re.sub(r'<think>[\s\S]*?</think>', '', answer).strip()
                return answer
            logger.warning(f"Dify chat {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Dify chat failed: {e}")
        return None


def _extract_workflow_outputs(result: dict | None) -> dict:
    """Extract Dify blocking workflow outputs across common response shapes."""
    if not result:
        return {}
    data = result.get("data", {})
    outputs = data.get("outputs") or {}
    if outputs:
        return outputs
    return data if isinstance(data, dict) else {}


async def batch_predict(
    customers: list[dict],
    store_name: str,
    store_industry: str,
    api_key: str,
) -> list[dict]:
    """
    Batch churn prediction through the churn workflow.

    Dify does not provide a native bulk workflow endpoint here, so this keeps
    the router contract stable by calling the same churn workflow per customer
    and returning one normalized item per customer.
    """
    results = []
    for customer in customers:
        visits = customer.get("visits") or []
        total_spent = sum(float(v.get("amount") or 0) for v in visits)
        visit_count = len(visits)
        days_ago = 999
        if visits:
            try:
                raw_date = str(visits[0].get("date") or "")
                visited_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).replace(tzinfo=None)
                days_ago = max(0, (datetime.utcnow() - visited_at).days)
            except Exception:
                days_ago = 999

        payload = {
            "inputs": {
                "store_name": store_name,
                "store_industry": store_industry,
                "customer_name": customer.get("name") or "",
                "total_spent": total_spent,
                "visit_count": visit_count,
                "days_ago": days_ago,
                "visit_history": str(visits),
            },
            "response_mode": "blocking",
            "user": customer.get("id") or customer.get("name") or "batch",
        }
        workflow_result = await _call_workflow(payload, api_key)
        outputs = _extract_workflow_outputs(workflow_result)
        score = outputs.get("risk_score") or outputs.get("churn_score")
        annual_value = outputs.get("annual_value") or outputs.get("clv")
        results.append({
            "customer_id": customer.get("id"),
            "name": customer.get("name"),
            "churn_score": float(score) if score not in (None, "") else None,
            "clv": float(annual_value) if annual_value not in (None, "") else None,
            "risk_level": outputs.get("risk_level"),
            "report": outputs.get("report") or outputs.get("text") or "",
            "source": "dify" if workflow_result else "unavailable",
        })
    return results
