"""
认证模块 Pydantic Schema — 请求/响应模型
"""
import re
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, field_validator


# ============================================================
# 请求模型
# ============================================================

class SendCodeRequest(BaseModel):
    """发送短信验证码"""
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class LoginByPhoneRequest(BaseModel):
    """手机号 + 验证码登录"""
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("验证码为 6 位数字")
        return v


class LoginByPasswordRequest(BaseModel):
    """手机号 + 密码登录"""
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class RegisterByPhoneRequest(BaseModel):
    """手机号 + 验证码 + 密码注册"""
    phone: str
    code: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("验证码为 6 位数字")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 50:
            raise ValueError("密码长度需在 8-50 位之间")
        return v


class RefreshTokenRequest(BaseModel):
    """刷新 access_token"""
    refresh_token: str


class LogoutRequest(BaseModel):
    """退出登录（加入黑名单）"""
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    """更新个人信息"""
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """修改密码"""
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 50:
            raise ValueError("新密码长度需在 8-50 位之间")
        return v


class ChangePhoneRequest(BaseModel):
    """更换手机号（需验证码）"""
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("验证码为 6 位数字")
        return v


# ============================================================
# 响应模型
# ============================================================

class TokenResponse(BaseModel):
    """JWT 令牌对"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access_token 剩余有效秒数


class UserInfoResponse(BaseModel):
    """用户基本信息"""
    id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    roles: List[str] = []
    store_id: Optional[str] = None
    created_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str


# ============================================================
# 二维码登录
# ============================================================

class QrGenerateResponse(BaseModel):
    """生成二维码登录会话"""
    qr_id: str
    qr_url: str
    qr_image: str  # base64 PNG 图片
    expires_in: int  # 有效期（秒）


class QrStatusResponse(BaseModel):
    """二维码状态查询"""
    status: str  # pending / scanned / confirmed / expired
    tokens: Optional[dict] = None
    user_name: Optional[str] = None


class QrConfirmRequest(BaseModel):
    """手机端确认登录（需要已登录）"""
    qr_id: str


class WechatQrResponse(BaseModel):
    """微信扫码登录 URL"""
    qr_url: str
    state: str
    expires_in: int


class WechatStatusResponse(BaseModel):
    """微信扫码登录状态"""
    status: str
    tokens: Optional[dict] = None
    message: Optional[str] = None


class WechatBindPasswordRequest(BaseModel):
    """微信首次扫码后，使用既有手机号密码绑定账号"""
    state: str
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v
