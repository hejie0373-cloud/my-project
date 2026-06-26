"""
用户路由：个人信息、角色信息、设置页接口
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_store_id
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    UserInfoResponse, MessageResponse,
    UpdateProfileRequest, ChangePasswordRequest, ChangePhoneRequest,
)
from app.services.auth_service import get_user_info
from app.utils.redis_client import verify_sms_code, delete_sms_code

router = APIRouter()


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="获取当前用户信息",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前登录用户的基本信息"""
    return await get_user_info(user=current_user, db=db)


@router.put(
    "/me",
    response_model=MessageResponse,
    summary="更新个人信息",
)
async def update_me(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新姓名和头像"""
    if data.name is not None:
        current_user.name = data.name
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    await db.commit()
    return MessageResponse(message="个人信息已更新")


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    summary="修改密码",
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改登录密码（需验证旧密码）"""
    if not current_user.password_hash or not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码不正确")
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    return MessageResponse(message="密码已修改")


@router.post(
    "/me/change-phone",
    response_model=MessageResponse,
    summary="更换手机号",
)
async def change_phone(
    data: ChangePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更换绑定手机号（需短信验证码）"""
    # 校验验证码
    if not await verify_sms_code(data.phone, data.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
    # 检查新手机号是否已被其他用户使用
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.phone == data.phone))
    existing = result.scalar_one_or_none()
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该手机号已被其他账号使用")
    # 更新手机号
    current_user.phone = data.phone
    await db.commit()
    await delete_sms_code(data.phone)
    return MessageResponse(message="手机号已更换")


@router.get(
    "/me/store",
    summary="获取当前用户的店铺 ID",
)
async def get_my_store(
    store_id: str = Depends(get_current_store_id),
    current_user: User = Depends(get_current_user),
):
    """返回当前用户绑定的店铺 ID，未绑定时返回 null"""
    return {"user_id": current_user.id, "store_id": store_id}
