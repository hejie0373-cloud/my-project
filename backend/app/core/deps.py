"""
FastAPI 依赖注入：当前用户、DB Session、角色守卫、店铺守卫
"""
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, Role, UserRole

# ============================================================
# OAuth2 Bearer Token 提取器
# ============================================================
oauth2_scheme = HTTPBearer(
    scheme_name="JWT",
    description="输入 Bearer {access_token}",
)


# ============================================================
# 当前用户依赖
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 JWT 解析用户 → 查 DB → 验证 is_active

    所有需要认证的接口必须依赖此函数。

    Raises:
        401: Token 无效或已过期
        403: 用户被禁用
    """
    token = credentials.credentials
    payload = decode_token(token)

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_INVALID",
        )

    # 从 DB 加载用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="USER_NOT_FOUND",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="USER_DISABLED",
        )

    return user


# ============================================================
# 当前用户角色列表
# ============================================================

async def get_current_user_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[str]:
    """获取当前用户的所有角色名列表（单次 JOIN 查询）"""
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == current_user.id)
    )
    return [row[0] for row in result.all()]


# ============================================================
# 当前店铺 ID（多店铺场景下从 JWT 中取）
# ============================================================

async def get_current_store_id(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[str]:
    """
    获取当前用户的 store_id

    优先级：
    1. 从 JWT payload 中取（已绑定店铺的场景）
    2. 从 DB user_roles 中取第一个非空 store_id
    3. 都为空时抛出 STORE_NOT_BOUND（Onboarding 前状态）
    """
    token = credentials.credentials
    payload = decode_token(token)

    # 先从 JWT 中取
    store_id = payload.get("store_id")
    if store_id:
        return store_id

    # 再从 DB 中取
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == current_user.id,
            UserRole.store_id.isnot(None),
        )
    )
    user_role = result.scalar_one_or_none()
    if user_role and user_role.store_id:
        return user_role.store_id

    return None


async def require_store(
    store_id: Optional[str] = Depends(get_current_store_id),
) -> str:
    """
    要求用户必须已绑定店铺
    未绑定时抛出 403（引导去 Onboarding）
    """
    if store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="STORE_NOT_BOUND",
        )
    return store_id


async def require_active_subscription(
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
) -> str:
    from app.services.billing_service import check_quota

    await check_quota(store_id, db, "customer_add")
    return store_id


def require_quota(quota_type: str):
    """配额检查守卫。quota_type: ai | campaign | export"""
    async def checker(
        store_id: str = Depends(require_store),
        db: AsyncSession = Depends(get_db),
    ) -> str:
        from app.services.billing_service import check_quota

        await check_quota(store_id, db, quota_type)
        return store_id

    return Depends(checker)


# ============================================================
# 角色守卫
# ============================================================

def require_role(*allowed_roles: str):
    """
    角色守卫工厂函数

    用法:
        @router.get("/admin")
        async def admin_endpoint(
            current_user: User = Depends(require_role("super_admin"))
        ):
            ...

    如果用户角色不在 allowed_roles 中 → 403
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # 单次 JOIN 查所有角色名
        result = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == current_user.id)
        )
        user_role_names = {row[0] for row in result.all()}

        if "super_admin" in user_role_names:
            return current_user

        if not user_role_names.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PERMISSION_DENIED",
            )

        return current_user

    return Depends(role_checker)


# ============================================================
# 越权防护工具
# ============================================================

def verify_store_access(obj_store_id: str, current_store_id: str, detail: str = "PERMISSION_DENIED"):
    """
    校验资源是否属于当前店铺（防越权）

    用法:
        verify_store_access(customer.store_id, current_store_id)
    """
    if obj_store_id != current_store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
