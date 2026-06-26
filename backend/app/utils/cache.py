"""Redis 缓存工具 — 提高命中率，减少 DB 和 Dify 调用"""
import json, logging

logger = logging.getLogger(__name__)

TTL_SHORT = 30      # 列表类数据
TTL_MEDIUM = 120    # 详情数据
TTL_LONG = 3600     # AI 评分结果
TTL_DAY = 86400     # 店铺信息


async def get(key: str) -> dict | list | None:
    try:
        from app.utils.redis_client import get_redis
        r = await get_redis()
        data = await r.get(key)
        if data:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(data)
        logger.debug(f"Cache MISS: {key}")
        return None
    except Exception:
        return None


async def set(key: str, data, ttl: int = TTL_MEDIUM) -> None:
    try:
        from app.utils.redis_client import get_redis
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(data, default=str, ensure_ascii=False))
    except Exception:
        pass


async def delete(key: str) -> None:
    try:
        from app.utils.redis_client import get_redis
        r = await get_redis()
        await r.delete(key)
        logger.debug(f"Cache DEL: {key}")
    except Exception:
        pass
