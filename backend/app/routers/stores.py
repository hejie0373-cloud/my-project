from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_store_id, get_current_user, get_current_user_roles
from app.db.session import get_db
from app.models.user import User, UserRole, Role
from app.models.store import Store
from app.models.subscription import Subscription
from app.schemas.store import StoreCreate, StoreOut, StoreUpdate

router = APIRouter()


@router.get("/{store_id}", response_model=StoreOut, summary="获取店铺信息")
async def get_store(
    store_id: str,
    current_user: User = Depends(get_current_user),
    current_store_id: str | None = Depends(get_current_store_id),
    roles: list[str] = Depends(get_current_user_roles),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(404, "店铺不存在")
    if "super_admin" not in roles and store.id != current_store_id:
        raise HTTPException(403, "PERMISSION_DENIED")
    return StoreOut(
        id=store.id, name=store.name, address=store.address,
        industryType=store.industry_type, logoUrl=store.logo_url,
        createdAt=store.created_at,
    )


@router.put("/{store_id}", response_model=StoreOut, summary="更新店铺信息")
async def update_store(
    store_id: str,
    data: StoreUpdate,
    current_user: User = Depends(get_current_user),
    current_store_id: str | None = Depends(get_current_store_id),
    roles: list[str] = Depends(get_current_user_roles),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(404, "店铺不存在")
    if "super_admin" not in roles and store.id != current_store_id:
        raise HTTPException(403, "PERMISSION_DENIED")
    if data.name is not None:
        store.name = data.name.strip()
    if data.address is not None:
        store.address = data.address
    if data.industryType is not None:
        store.industry_type = data.industryType
    await db.commit()
    await db.refresh(store)
    return StoreOut(
        id=store.id, name=store.name, address=store.address,
        industryType=store.industry_type, logoUrl=store.logo_url,
        createdAt=store.created_at,
    )


@router.post("", response_model=StoreOut, status_code=201, summary="创建店铺")
async def create_store(
    data: StoreCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == current_user.id,
            UserRole.store_id.isnot(None),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "已有店铺，不能重复创建")

    store = Store(
        name=data.name.strip(),
        address=data.address,
        industry_type=data.industryType,
        owner_id=current_user.id,
    )
    db.add(store)
    await db.flush()

    role_result = await db.execute(select(Role).where(Role.name == "store_owner"))
    role = role_result.scalar_one_or_none()
    if role:
        db.add(UserRole(user_id=current_user.id, role_id=role.id, store_id=store.id))

    db.add(Subscription(store_id=store.id, plan_name="free", status="active"))
    await db.commit()
    await db.refresh(store)

    return StoreOut(
        id=store.id, name=store.name, address=store.address,
        industryType=store.industry_type, logoUrl=store.logo_url,
        createdAt=store.created_at,
    )
