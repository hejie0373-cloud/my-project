"""微信测试号 OAuth 扫码登录服务。"""
import json
import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.user import Role, User, UserRole
from app.utils.redis_client import get_redis

logger = logging.getLogger(__name__)

WECHAT_STATE_PREFIX = "wechat_state:"
WECHAT_STATE_TTL = 300


def _state_key(state: str) -> str:
    return f"{WECHAT_STATE_PREFIX}{state}"


async def generate_qr_url() -> dict:
    """生成微信 OAuth 授权 URL，并初始化 Redis 轮询状态。"""
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET or not settings.WECHAT_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WECHAT_CONFIG_MISSING",
        )

    state = secrets.token_urlsafe(16)
    query = urlencode({
        "appid": settings.WECHAT_APP_ID,
        "redirect_uri": settings.WECHAT_REDIRECT_URI,
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": state,
    })
    qr_url = f"https://open.weixin.qq.com/connect/oauth2/authorize?{query}#wechat_redirect"

    r = await get_redis()
    await r.setex(_state_key(state), WECHAT_STATE_TTL, json.dumps({"status": "pending"}, ensure_ascii=False))
    return {"qr_url": qr_url, "state": state, "expires_in": WECHAT_STATE_TTL}


async def handle_callback(code: str, state: str, db: AsyncSession) -> bool:
    """处理微信 OAuth 回调，并把登录 token 写入 Redis。"""
    r = await get_redis()
    data_raw = await r.get(_state_key(state))
    if not data_raw:
        logger.warning("微信扫码 state 无效或已过期: %s", state)
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_res = await client.get(
                "https://api.weixin.qq.com/sns/oauth2/access_token",
                params={
                    "appid": settings.WECHAT_APP_ID,
                    "secret": settings.WECHAT_APP_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_res.json()
            if "errcode" in token_data:
                logger.warning("微信 access_token 换取失败: %s", token_data)
                return False

            access_token = token_data["access_token"]
            openid = token_data["openid"]
            user_res = await client.get(
                "https://api.weixin.qq.com/sns/userinfo",
                params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
            )
            user_data = user_res.json()
            if "errcode" in user_data:
                logger.warning("微信 userinfo 获取失败: %s", user_data)
                return False
    except Exception as exc:
        logger.exception("微信回调处理失败: %s", exc)
        return False

    user = await _get_wechat_user(openid, user_data, db)
    if not user:
        await r.setex(
            _state_key(state),
            30,
            json.dumps(
                {
                    "status": "unbound",
                    "message": "WECHAT_NOT_BOUND",
                    "openid": openid,
                    "user_data": user_data,
                },
                ensure_ascii=False,
            ),
        )
        return False

    tokens = await _create_tokens_for_user(user, db)
    await r.setex(
        _state_key(state),
        30,
        json.dumps({"status": "confirmed", "tokens": tokens}, ensure_ascii=False),
    )
    return True


async def get_login_status(state: str) -> dict:
    """读取微信扫码登录状态。"""
    r = await get_redis()
    data_raw = await r.get(_state_key(state))
    if not data_raw:
        return {"status": "expired"}
    return json.loads(data_raw)


async def bind_wechat_by_password(state: str, phone: str, password: str, db: AsyncSession) -> dict:
    """微信首次扫码后，绑定到同手机号的既有账号。"""
    r = await get_redis()
    data_raw = await r.get(_state_key(state))
    if not data_raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WECHAT_STATE_EXPIRED")

    state_data = json.loads(data_raw)
    if state_data.get("status") != "unbound" or not state_data.get("openid"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WECHAT_STATE_NOT_BINDABLE")

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="USER_DISABLED")

    existing = await db.execute(select(User).where(User.wechat_openid == state_data["openid"]))
    existing_user = existing.scalar_one_or_none()
    if existing_user and existing_user.id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WECHAT_ALREADY_BOUND")

    user_data = state_data.get("user_data") or {}
    user.wechat_openid = state_data["openid"]
    user.wechat_nickname = user_data.get("nickname") or user.wechat_nickname
    user.wechat_avatar = user_data.get("headimgurl") or user.wechat_avatar
    if user.wechat_avatar and not user.avatar_url:
        user.avatar_url = user.wechat_avatar
    await db.commit()
    await db.refresh(user)

    tokens = await _create_tokens_for_user(user, db)
    await r.setex(
        _state_key(state),
        30,
        json.dumps({"status": "confirmed", "tokens": tokens}, ensure_ascii=False),
    )
    return {"status": "confirmed", "tokens": tokens}


async def _get_wechat_user(openid: str, user_data: dict, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.wechat_openid == openid))
    user = result.scalar_one_or_none()
    nickname = user_data.get("nickname") or "微信用户"
    avatar = user_data.get("headimgurl")

    if not user:
        logger.info("微信 openid 未绑定既有账号，拒绝自动创建商家账号: openid=%s", openid)
        return None

    user.wechat_nickname = nickname
    user.wechat_avatar = avatar
    if avatar and not user.avatar_url:
        user.avatar_url = avatar
    await db.commit()
    await db.refresh(user)
    return user


async def _create_tokens_for_user(user: User, db: AsyncSession) -> dict:
    roles_result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    role_names = [row[0] for row in roles_result.all()]

    store_result = await db.execute(
        select(UserRole.store_id).where(
            UserRole.user_id == user.id,
            UserRole.store_id.isnot(None),
        ).limit(1)
    )
    store_id = store_result.scalar_one_or_none()

    payload = {"sub": user.id, "roles": role_names}
    if store_id:
        payload["store_id"] = store_id

    access_token, _, expires_in = create_access_token(payload)
    refresh_token, _ = create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }
