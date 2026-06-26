"""
客户与到店记录路由
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_active_subscription, require_store, verify_store_access
from app.db.session import get_db
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerOut,
    CustomerListResponse,
    VisitCreate,
    VisitOut,
    ImportProgress,
)
from app.services.customer_service import (
    list_customers,
    get_customer_detail,
    create_customer,
    update_customer,
    delete_customer,
    revoke_customer_consent,
)
from app.services.visit_service import create_visit, get_visit_list
from app.services.import_service import create_import_task, get_progress, process_csv_import
from app.db.session import get_session_factory

router = APIRouter()


# ============================================================
# 客户 CRUD
# ============================================================

@router.get("", response_model=CustomerListResponse, summary="客户列表")
async def list_customers_endpoint(
    search: Optional[str] = Query(None, description="姓名/手机号搜索"),
    risk_level: Optional[str] = Query(None, description="风险等级: high/medium/low"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    """
    客户列表（分页 + 搜索 + 风险筛选）

    - search：优先 ES 全文搜索，fallback MySQL LIKE
    - risk_level：high(churn>60) / medium(30-60) / low(<30)
    """
    return await list_customers(
        store_id=store_id,
        db=db,
        search=search,
        risk_level=risk_level,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CustomerOut, status_code=201, summary="创建客户")
async def create_customer_endpoint(
    data: CustomerCreate,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    """
    创建新客户

    - 同店铺内手机号不可重复
    - 自动同步到 ES 搜索索引
    """
    customer = await create_customer(store_id=store_id, data=data, db=db)
    # 返回完整详情
    return await get_customer_detail(customer_id=customer.id, store_id=store_id, db=db)


@router.get("/{customer_id}", response_model=CustomerOut, summary="客户详情")
async def get_customer_endpoint(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    """
    客户详情（含 AI 评分 + 最近 10 条到店记录）
    """
    return await get_customer_detail(customer_id=customer_id, store_id=store_id, db=db)


@router.put("/{customer_id}", response_model=CustomerOut, summary="更新客户")
async def update_customer_endpoint(
    customer_id: str,
    data: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
):
    """
    更新客户信息（仅更新提交的非空字段）
    """
    customer = await update_customer(customer_id=customer_id, store_id=store_id, data=data, db=db)
    return await get_customer_detail(customer_id=customer.id, store_id=store_id, db=db)


@router.post("/{customer_id}/revoke-consent", summary="撤回客户授权")
async def revoke_consent_endpoint(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """撤回客户授权 → 自动软删除 + ES 清理 + 记录时间戳"""
    await revoke_customer_consent(customer_id=customer_id, store_id=store_id, db=db)
    return {"message": "客户授权已撤回，数据已清理"}


@router.delete("/{customer_id}", summary="删除客户（软删除）")
async def delete_customer_endpoint(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """
    软删除客户（is_deleted=True），从 ES 移除索引
    """
    await delete_customer(customer_id=customer_id, store_id=store_id, db=db)
    return {"message": "客户已删除"}


# ============================================================
# 到店记录
# ============================================================

@router.post("/{customer_id}/visits", response_model=VisitOut, status_code=201, summary="录入到店记录")
async def create_visit_endpoint(
    customer_id: str,
    data: VisitCreate,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """
    为客户录入一条到店记录

    录入后自动触发客户流失评分重算
    """
    visit = await create_visit(
        customer_id=customer_id,
        store_id=store_id,
        data=data,
        db=db,
    )
    return VisitOut(
        id=visit.id,
        customer_id=visit.customer_id,
        store_id=visit.store_id,
        visited_at=visit.visited_at,
        service_type=visit.service_type,
        staff_name=visit.staff_name,
        amount=float(visit.amount),
        payment_method=visit.payment_method,
        feedback=visit.feedback,
        source=visit.source,
        created_at=visit.created_at,
    )


@router.get("/{customer_id}/visits", response_model=list[VisitOut], summary="到店记录列表")
async def list_visits_endpoint(
    customer_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
    db: AsyncSession = Depends(get_db),
):
    """获取客户的到店记录列表"""
    visits = await get_visit_list(customer_id=customer_id, store_id=store_id, db=db, limit=limit)
    return [
        VisitOut(
            id=v.id,
            customer_id=v.customer_id,
            store_id=v.store_id,
            visited_at=v.visited_at,
            service_type=v.service_type,
            staff_name=v.staff_name,
            amount=float(v.amount),
            payment_method=v.payment_method,
            feedback=v.feedback,
            source=v.source,
            created_at=v.created_at,
        )
        for v in visits
    ]


# ============================================================
# CSV 导入
# ============================================================

@router.post("/import", summary="上传 CSV 导入客户")
async def import_csv_endpoint(
    file: UploadFile = File(..., description="CSV 文件"),
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
):
    """
    上传 CSV 文件批量导入客户

    - 支持字段：name(必填), phone(必填), email, gender, birthday, address, preferred_contact
    - 支持到店字段：visited_at, service_type, amount, payment_method, feedback
    - 返回 task_id，前端轮询 GET /customers/import/{task_id} 获取进度
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传 .csv 格式的文件")

    # 创建任务
    task_id = await create_import_task()

    # 保存到 backend 容器与 Celery worker 共享的挂载目录。
    upload_dir = "/app/tmp/imports"
    os.makedirs(upload_dir, exist_ok=True)
    tmp_path = f"{upload_dir}/{task_id}.csv"
    with open(tmp_path, "wb") as tmp:
        content = await file.read()
        tmp.write(content)

    # 异步处理（开发阶段直接同步执行，生产环境用 Celery）
    from app.core.config import settings
    if settings.ENVIRONMENT == "development":
        import asyncio
        asyncio.create_task(
            process_csv_import(
                task_id=task_id,
                file_path=tmp_path,
                store_id=store_id,
                db_session_factory=get_session_factory,
            )
        )
    else:
        from app.tasks.import_task import process_csv
        process_csv.delay(task_id=task_id, file_path=tmp_path, store_id=store_id)

    return {"task_id": task_id, "message": "导入任务已创建"}


@router.get("/import/{task_id}", response_model=ImportProgress, summary="查询导入进度")
async def get_import_progress_endpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
    store_id: str = Depends(require_store),
):
    """
    查询 CSV 导入进度

    返回 total/success/failed/errors/status
    - status: processing | done | error
    """
    progress = await get_progress(task_id)
    return ImportProgress(**progress)
