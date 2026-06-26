"""WebSocket 实时通知处理。"""
import logging
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect

from app.core.security import decode_token

logger = logging.getLogger(__name__)

_connections: Dict[str, List[WebSocket]] = {}


async def start_redis_listener():
    """监听 Redis Pub/Sub，并把通知广播到对应店铺的 WebSocket 连接。"""
    try:
        from app.utils.redis_client import get_pubsub_redis

        redis = await get_pubsub_redis()
        pubsub = redis.pubsub()
        await pubsub.psubscribe("notify:*")
        logger.info("Redis Pub/Sub 监听已启动")

        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue

            channel = message["channel"]
            store_id = channel.replace("notify:", "")
            data = message["data"]

            if store_id not in _connections:
                continue

            dead = []
            for ws in _connections[store_id]:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                _connections[store_id].remove(ws)

    except Exception as exc:
        logger.warning("Redis Pub/Sub 监听失败: %s", exc)


async def handle_connection(websocket: WebSocket, store_id: str, token: str):
    """处理单个 WebSocket 连接。"""
    try:
        payload = decode_token(token)
        ws_store_id = payload.get("store_id")
        roles = payload.get("roles", [])
        if "super_admin" not in roles and ws_store_id != store_id:
            await websocket.close(code=4003, reason="PERMISSION_DENIED")
            return
    except Exception:
        await websocket.close(code=4001, reason="TOKEN_INVALID")
        return

    await websocket.accept()
    logger.info("WebSocket 已连接 store_id=%s", store_id)
    _connections.setdefault(store_id, []).append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("WebSocket 已断开 store_id=%s", store_id)
    finally:
        if store_id in _connections and websocket in _connections[store_id]:
            _connections[store_id].remove(websocket)
