"""
GitHub Actions Webhook 接收端点
接收 CI/CD 事件 → 推送 Dify 工作流 → 通知/告警/记录
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 部署历史（生产环境用 Redis/DB）
_deploy_history: list[dict] = []


@router.post("/deploy", summary="GitHub Actions 部署事件")
async def deploy_webhook(request: Request):
    """
    接收 GitHub Actions 发送的部署事件

    事件类型（由 Actions 在 body 中指定）:
    - deploy_started: 部署开始
    - test_passed / test_failed: 测试阶段
    - build_success / build_failed: 构建阶段
    - deploy_success / deploy_failed: 部署阶段

    GitHub Actions 调用示例:
      curl -X POST https://your-server/webhooks/deploy \
        -H "Content-Type: application/json" \
        -d '{"event":"deploy_started","repo":"keliu","branch":"main","commit":"abc123","actor":"username"}'
    """
    body = await request.json()
    event = body.get("event", "unknown")
    repo = body.get("repo", "keliu")
    branch = body.get("branch", "main")
    commit = body.get("commit", "")[:8]
    actor = body.get("actor", "CI")
    error = body.get("error", "")
    timestamp = datetime.utcnow().isoformat()

    record = {
        "timestamp": timestamp, "event": event, "repo": repo,
        "branch": branch, "commit": commit, "actor": actor, "error": error,
    }
    _deploy_history.append(record)
    if len(_deploy_history) > 100:
        _deploy_history.pop(0)

    # 事件日志
    emoji = {
        "deploy_started": "🚀", "test_passed": "✅", "test_failed": "❌",
        "build_success": "📦", "build_failed": "💥",
        "deploy_success": "🎉", "deploy_failed": "🔥",
    }.get(event, "📢")

    logger.info(f"{emoji} [{event}] {repo}@{branch} commit={commit} by {actor}")

    # 失败事件 → 推送到 Dify 诊断工作流
    if "failed" in event and settings.DIFY_INSIGHT_API_KEY:
        await _trigger_dify_diagnose(record)

    # 部署成功/失败 → 推送通知工作流
    if event in ("deploy_success", "deploy_failed"):
        await _trigger_dify_notify(record)

    return {"status": "ok", "event": event, "history_count": len(_deploy_history)}


@router.get("/deploy/history", summary="部署历史")
async def deploy_history(limit: int = 20):
    """查看最近部署记录"""
    return {
        "total": len(_deploy_history),
        "items": list(reversed(_deploy_history[-limit:])),
    }


async def _trigger_dify_notify(record: dict):
    """触发 Dify 部署通知工作流"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{settings.DIFY_API_URL}/v1/workflows/run",
                headers={"Authorization": f"Bearer {settings.DIFY_INSIGHT_API_KEY}"},
                json={
                    "inputs": {
                        "event": record["event"],
                        "repo": record["repo"],
                        "branch": record["branch"],
                        "commit": record["commit"],
                        "actor": record["actor"],
                        "error": record["error"],
                        "timestamp": record["timestamp"],
                    },
                    "response_mode": "blocking",
                    "user": "github-actions",
                },
            )
    except Exception as e:
        logger.warning(f"Dify 通知推送失败: {e}")


async def _trigger_dify_diagnose(record: dict):
    """触发 Dify 失败诊断工作流"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                f"{settings.DIFY_API_URL}/v1/workflows/run",
                headers={"Authorization": f"Bearer {settings.DIFY_INSIGHT_API_KEY}"},
                json={
                    "inputs": {
                        "event": record["event"],
                        "repo": record["repo"],
                        "commit": record["commit"],
                        "error_log": record["error"],
                        "pipeline_stage": record["event"].replace("_failed", ""),
                    },
                    "response_mode": "blocking",
                    "user": "github-actions",
                },
            )
    except Exception as e:
        logger.warning(f"Dify 诊断推送失败: {e}")
