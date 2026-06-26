"""
Redis 客户端封装。

提供同步和异步两类客户端：
- 同步：slowapi 限流、Celery broker。
- 异步：验证码、token 黑名单、导入进度、缓存、WebSocket Pub/Sub。
"""
import json
from typing import Optional

import redis as sync_redis
import redis.asyncio as aioredis

from app.core.config import settings


sync_client: Optional[sync_redis.Redis] = None
async_client: Optional[aioredis.Redis] = None
pubsub_client: Optional[aioredis.Redis] = None


def get_sync_redis() -> sync_redis.Redis:
    """获取同步 Redis 客户端。"""
    global sync_client
    if sync_client is None:
        sync_client = sync_redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return sync_client


async def get_redis() -> aioredis.Redis:
    """获取异步 Redis 客户端。"""
    global async_client
    if async_client is None:
        async_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return async_client


async def get_pubsub_redis() -> aioredis.Redis:
    """获取 Pub/Sub 专用 Redis 客户端。"""
    global pubsub_client
    if pubsub_client is None:
        pubsub_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=None,
        )
    return pubsub_client


async def close_redis():
    """关闭异步 Redis 连接。"""
    global async_client, pubsub_client
    if async_client is not None:
        await async_client.aclose()
        async_client = None
    if pubsub_client is not None:
        await pubsub_client.aclose()
        pubsub_client = None


SMS_CODE_PREFIX = "sms_code"
SMS_CODE_TTL = 300
SMS_RATE_LIMIT_TTL = 60


async def store_sms_code(phone: str, code: str) -> None:
    """存储短信验证码。"""
    r = await get_redis()
    await r.setex(f"{SMS_CODE_PREFIX}:{phone}", SMS_CODE_TTL, code)


async def verify_sms_code(phone: str, code: str) -> bool:
    """校验短信验证码。"""
    r = await get_redis()
    stored = await r.get(f"{SMS_CODE_PREFIX}:{phone}")
    return stored == code if stored is not None else False


async def delete_sms_code(phone: str) -> None:
    """删除短信验证码。"""
    r = await get_redis()
    await r.delete(f"{SMS_CODE_PREFIX}:{phone}")


async def check_sms_rate_limit(phone: str) -> bool:
    """限制同一手机号 60 秒内只能发送一次验证码。"""
    r = await get_redis()
    key = f"{SMS_CODE_PREFIX}:rate:{phone}"
    if await r.exists(key):
        return False
    await r.setex(key, SMS_RATE_LIMIT_TTL, "1")
    return True


TOKEN_BLACKLIST_PREFIX = "token_blacklist"


async def add_to_blacklist(jti: str, ttl: int) -> None:
    """将 refresh token 的 jti 加入黑名单。"""
    r = await get_redis()
    await r.setex(f"{TOKEN_BLACKLIST_PREFIX}:{jti}", ttl, "1")


async def is_blacklisted(jti: str) -> bool:
    """检查 token jti 是否已进入黑名单。"""
    r = await get_redis()
    return await r.exists(f"{TOKEN_BLACKLIST_PREFIX}:{jti}") > 0


IMPORT_PREFIX = "import_progress"
IMPORT_TTL = 3600


async def set_import_progress(task_id: str, progress: dict) -> None:
    """保存 CSV 导入进度。"""
    r = await get_redis()
    await r.setex(
        f"{IMPORT_PREFIX}:{task_id}",
        IMPORT_TTL,
        json.dumps(progress, ensure_ascii=False, default=str),
    )


async def get_import_progress(task_id: str) -> dict | None:
    """读取 CSV 导入进度。"""
    r = await get_redis()
    data = await r.get(f"{IMPORT_PREFIX}:{task_id}")
    return json.loads(data) if data else None


async def publish(channel: str, message: dict) -> None:
    """向指定 Pub/Sub 频道发布消息。"""
    r = await get_redis()
    await r.publish(channel, json.dumps(message, ensure_ascii=False))
