"""认证业务逻辑：注册、登录、刷新、退出。"""
import logging
import random
import secrets
import string

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_refresh_token_ttl,
    hash_password,
    verify_password,
)
from app.models.user import Role, User, UserRole
from app.schemas.auth import TokenResponse, UserInfoResponse
from app.utils.redis_client import (
    add_to_blacklist,
    check_sms_rate_limit,
    delete_sms_code,
    is_blacklisted,
    store_sms_code,
    verify_sms_code,
)

logger = logging.getLogger(__name__)


def generate_verification_code() -> str:
    """生成 6 位数字验证码。"""
    return "".join(random.choices(string.digits, k=6))


async def send_verification_code(phone: str) -> str:
    """发送短信验证码。开发环境会返回验证码，方便本地调试。"""
    if not await check_sms_rate_limit(phone):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证码发送过于频繁，请 60 秒后再试",
        )

    code = generate_verification_code()
    await store_sms_code(phone, code)

    if settings.ENVIRONMENT == "development":
        logger.info("[DEV] verification_code phone=%s code=%s", phone, code)
        print(f"\n{'=' * 50}")
        print("  短信验证码（开发模式）")
        print(f"  手机号: {phone}")
        print(f"  验证码: {code}")
        print("  有效期: 5 分钟")
        print(f"{'=' * 50}\n")
        return code

    from app.services.notification_service import SMSProvider

    provider = SMSProvider()
    success = await provider.send(phone, code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="短信发送失败，请稍后再试",
        )

    return ""


async def login_by_phone(
    phone: str,
    code: str,
    db: AsyncSession,
) -> dict:
    """手机号 + 验证码登录。新用户返回 is_new_user，引导前端注册。"""
    if not await verify_sms_code(phone, code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        return {"is_new_user": True, "phone": phone}

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    await delete_sms_code(phone)
    token_response = await _generate_token_response(user, db)
    return {
        "is_new_user": False,
        **token_response.model_dump(),
    }


async def login_by_password(
    phone: str,
    password: str,
    db: AsyncSession,
) -> TokenResponse:
    """手机号 + 密码登录。"""
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    return await _generate_token_response(user, db)


async def register_by_phone(
    phone: str,
    code: str,
    password: str,
    db: AsyncSession,
) -> TokenResponse:
    """手机号 + 验证码 + 密码注册。"""
    if not await verify_sms_code(phone, code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )

    result = await db.execute(select(User).where(User.phone == phone))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该手机号已注册，请直接登录",
        )

    user = User(
        phone=phone,
        name=f"用户{phone[-4:]}_{secrets.token_hex(2)}",
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    result = await db.execute(select(Role).where(Role.name == "store_owner"))
    store_owner_role = result.scalar_one_or_none()
    if store_owner_role:
        db.add(UserRole(user_id=user.id, role_id=store_owner_role.id, store_id=None))

    await db.commit()
    await db.refresh(user)
    await delete_sms_code(phone)
    return await _generate_token_response(user, db)


async def refresh_access_token(
    refresh_token: str,
    db: AsyncSession,
) -> TokenResponse:
    """使用 refresh_token 换取新的 access_token 和 refresh_token。"""
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOKEN_TYPE_INVALID")

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOKEN_INVALID")

    if await is_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOKEN_REVOKED")

    await add_to_blacklist(jti, get_refresh_token_ttl(payload))

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="USER_NOT_FOUND_OR_DISABLED")

    return await _generate_token_response(user, db)


async def logout(refresh_token: str) -> dict:
    """退出登录，将 refresh_token 加入黑名单。"""
    try:
        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if jti:
            ttl = get_refresh_token_ttl(payload)
            await add_to_blacklist(jti, ttl)
            logger.info("refresh token 已加入黑名单: jti=%s ttl=%ss", jti, ttl)
    except Exception:
        pass
    return {"message": "退出成功"}


async def get_user_info(user: User, db: AsyncSession) -> UserInfoResponse:
    """获取当前用户信息，包含角色列表和当前店铺 ID。"""
    result = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    user_roles = result.scalars().all()

    roles = []
    store_id = None
    for user_role in user_roles:
        role_result = await db.execute(select(Role).where(Role.id == user_role.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            roles.append(role.name)
        if store_id is None and user_role.store_id:
            store_id = user_role.store_id

    return UserInfoResponse(
        id=user.id,
        name=user.name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        roles=roles,
        store_id=store_id,
        created_at=user.created_at,
    )


async def _generate_token_response(user: User, db: AsyncSession) -> TokenResponse:
    """生成 access_token + refresh_token。"""
    result = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    user_roles = result.scalars().all()

    role_names = []
    store_id = None
    for user_role in user_roles:
        role_result = await db.execute(select(Role).where(Role.id == user_role.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            role_names.append(role.name)
        if store_id is None and user_role.store_id:
            store_id = user_role.store_id

    token_data = {"sub": user.id, "roles": role_names}
    if store_id:
        token_data["store_id"] = store_id

    access_token, access_jti, expires_in = create_access_token(token_data)
    refresh_token, refresh_jti = create_refresh_token(user.id)
    logger.info(
        "token 已生成 user_id=%s access_jti=%s refresh_jti=%s",
        user.id,
        access_jti,
        refresh_jti,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
