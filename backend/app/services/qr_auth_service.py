"""二维码扫码登录服务。"""
import base64
import io
import json
import logging
import secrets
from typing import Optional

import qrcode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import Role, UserRole
from app.utils.redis_client import get_redis

logger = logging.getLogger(__name__)

QR_SESSION_TTL = 300
QR_STATUS_PENDING = "pending"
QR_STATUS_SCANNED = "scanned"
QR_STATUS_CONFIRMED = "confirmed"
QR_STATUS_EXPIRED = "expired"


def _qr_key(qr_id: str) -> str:
    return f"qr_login:{qr_id}"


async def generate_qr_session() -> dict:
    """生成新的二维码登录会话。"""
    qr_id = secrets.token_urlsafe(32)
    frontend_url = settings.QR_CONFIRM_BASE_URL or "http://localhost:5173"
    qr_url = f"{frontend_url}/auth/qr-confirm/{qr_id}"

    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_image = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    r = await get_redis()
    session_data = {"status": QR_STATUS_PENDING, "qr_url": qr_url}
    await r.setex(_qr_key(qr_id), QR_SESSION_TTL, json.dumps(session_data, ensure_ascii=False))

    return {"qr_id": qr_id, "qr_url": qr_url, "qr_image": qr_image, "expires_in": QR_SESSION_TTL}


async def get_qr_status(qr_id: str) -> dict:
    """查询二维码登录会话状态。"""
    r = await get_redis()
    data_raw = await r.get(_qr_key(qr_id))
    if not data_raw:
        return {"status": QR_STATUS_EXPIRED}
    return json.loads(data_raw)


async def mark_qr_scanned(qr_id: str) -> bool:
    """标记二维码已被扫描。"""
    r = await get_redis()
    data_raw = await r.get(_qr_key(qr_id))
    if not data_raw:
        return False

    data = json.loads(data_raw)
    data["status"] = QR_STATUS_SCANNED
    ttl = await r.ttl(_qr_key(qr_id))
    await r.setex(_qr_key(qr_id), max(ttl, 60), json.dumps(data, ensure_ascii=False))
    return True


async def confirm_qr_login(
    qr_id: str,
    user_id: str,
    user_name: str,
    store_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> dict:
    """确认二维码登录，并把 token 写入 Redis 会话供桌面端轮询读取。"""
    r = await get_redis()
    data_raw = await r.get(_qr_key(qr_id))
    if not data_raw:
        return {"success": False, "error": "二维码会话已过期"}

    data = json.loads(data_raw)
    role_names: list[str] = []
    if db is not None:
        roles_result = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        role_names = [row[0] for row in roles_result.all()]

    token_data = {"sub": user_id, "roles": role_names}
    if store_id:
        token_data["store_id"] = store_id

    access_token, _, expires_in = create_access_token(token_data)
    refresh_token, _ = create_refresh_token(user_id)
    tokens = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }

    data["status"] = QR_STATUS_CONFIRMED
    data["tokens"] = tokens
    data["user_name"] = user_name
    await r.setex(_qr_key(qr_id), 30, json.dumps(data, ensure_ascii=False))

    return {"success": True, "tokens": tokens}
