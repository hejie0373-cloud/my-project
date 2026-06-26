"""认证路由：注册、登录、刷新、退出、扫码登录。"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginByPasswordRequest,
    LoginByPhoneRequest,
    LogoutRequest,
    MessageResponse,
    QrConfirmRequest,
    QrGenerateResponse,
    QrStatusResponse,
    RefreshTokenRequest,
    RegisterByPhoneRequest,
    SendCodeRequest,
    TokenResponse,
    WechatBindPasswordRequest,
    WechatQrResponse,
    WechatStatusResponse,
)
from app.services.auth_service import (
    login_by_password,
    login_by_phone,
    logout,
    refresh_access_token,
    register_by_phone,
    send_verification_code,
)
from app.services.qr_auth_service import confirm_qr_login, generate_qr_session, get_qr_status
from app.services.wechat_service import bind_wechat_by_password, generate_qr_url, get_login_status, handle_callback

router = APIRouter()


@router.post("/send-code", response_model=MessageResponse, summary="发送短信验证码")
@limiter.limit("3/minute")
async def send_code(request: Request, data: SendCodeRequest):
    code = await send_verification_code(data.phone)
    if settings.ENVIRONMENT == "development" and code:
        return MessageResponse(message=f"验证码已发送（开发模式：{code}）")
    return MessageResponse(message="验证码已发送")


@router.post("/login/phone", summary="手机号验证码登录")
async def login_phone(
    data: LoginByPhoneRequest,
    db: AsyncSession = Depends(get_db),
):
    return await login_by_phone(phone=data.phone, code=data.code, db=db)


@router.post("/login/password", response_model=TokenResponse, summary="手机号密码登录")
@limiter.limit("5/minute")
async def login_password(
    request: Request,
    data: LoginByPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    return await login_by_password(phone=data.phone, password=data.password, db=db)


@router.post("/register/phone", response_model=TokenResponse, status_code=201, summary="手机号注册")
async def register_phone(
    data: RegisterByPhoneRequest,
    db: AsyncSession = Depends(get_db),
):
    return await register_by_phone(phone=data.phone, code=data.code, password=data.password, db=db)


@router.post("/refresh", response_model=TokenResponse, summary="刷新 access token")
async def refresh(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    return await refresh_access_token(refresh_token=data.refresh_token, db=db)


@router.post("/logout", response_model=MessageResponse, summary="退出登录")
async def logout_endpoint(data: LogoutRequest):
    return await logout(refresh_token=data.refresh_token)


@router.post("/qr/generate", response_model=QrGenerateResponse, summary="生成扫码登录二维码")
async def generate_qr(request: Request):
    return await generate_qr_session()


@router.get("/qr/status/{qr_id}", response_model=QrStatusResponse, summary="查询扫码登录状态")
async def get_qr_status_endpoint(qr_id: str):
    return await get_qr_status(qr_id)


@router.post("/qr/confirm", response_model=MessageResponse, summary="确认扫码登录")
async def confirm_qr(
    data: QrConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result_store = await db.execute(
        select(UserRole).where(
            UserRole.user_id == current_user.id,
            UserRole.store_id.isnot(None),
        ).limit(1)
    )
    user_role = result_store.scalar_one_or_none()
    store_id = user_role.store_id if user_role else None

    result = await confirm_qr_login(
        qr_id=data.qr_id,
        user_id=str(current_user.id),
        user_name=current_user.name or current_user.phone or "用户",
        store_id=store_id,
        db=db,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    return MessageResponse(message="登录确认成功")


@router.get("/wechat/qr-url", response_model=WechatQrResponse, summary="获取微信扫码登录 URL")
async def get_wechat_qr_url():
    return await generate_qr_url()


@router.get("/wechat/callback", summary="微信 OAuth 回调")
async def wechat_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    success = await handle_callback(code=code, state=state, db=db)
    if success:
        return HTMLResponse(
            content="<html><body><h2>登录成功，请返回电脑查看</h2></body></html>",
            media_type="text/html; charset=utf-8",
        )
    return HTMLResponse(
        content="<html><body><h2>登录失败，请重新扫码</h2></body></html>",
        status_code=400,
        media_type="text/html; charset=utf-8",
    )


@router.get("/wechat/status/{state}", response_model=WechatStatusResponse, summary="轮询微信扫码登录状态")
async def get_wechat_status(state: str):
    return await get_login_status(state)


@router.post("/wechat/bind-password", response_model=WechatStatusResponse, summary="微信扫码后绑定既有账号")
async def bind_wechat_password(
    data: WechatBindPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    return await bind_wechat_by_password(
        state=data.state,
        phone=data.phone,
        password=data.password,
        db=db,
    )
