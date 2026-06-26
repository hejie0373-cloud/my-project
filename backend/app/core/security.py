"""
安全工具函数：JWT 生成/验证、密码哈希、Token 黑名单
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

# ============================================================
# 密码哈希
# ============================================================


def hash_password(plain: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ============================================================
# JWT 生成
# ============================================================

def _generate_jti() -> str:
    """生成唯一的 JWT ID"""
    return uuid.uuid4().hex


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, int]:
    """
    生成 access_token
    返回: (token_string, jti, expires_in_seconds)

    payload 包含: sub (user_id), jti, role, store_id, exp, type="access"
    """
    to_encode = data.copy()
    jti = _generate_jti()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expire = datetime.utcnow() + timedelta(seconds=expires_in)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": jti,
        "type": "access",
    })

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt, jti, expires_in


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """
    生成 refresh_token
    返回: (token_string, jti)

    payload 只含 sub, jti, type="refresh"
    有效期 7 天
    """
    jti = _generate_jti()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": user_id,
        "jti": jti,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt, jti


# ============================================================
# JWT 验证
# ============================================================

def decode_token(token: str) -> dict:
    """
    解码并验证 JWT token
    - 捕获过期/无效签名等异常，统一抛出 401
    - 不检查黑名单（由调用方决定）
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_EXPIRED",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_INVALID",
        )


def get_refresh_token_ttl(payload: dict) -> int:
    """
    从 refresh_token payload 计算剩余有效期（秒）
    用于设置黑名单 TTL
    """
    exp = payload.get("exp", 0)
    now = datetime.utcnow().timestamp()
    return max(0, int(exp - now))
