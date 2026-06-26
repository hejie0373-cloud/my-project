"""第三方支付回调路由。"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.billing import PaymentOrderOut
from app.services.billing_service import (
    confirm_alipay_return_public,
    handle_alipay_notify,
    sync_alipay_order_public,
)

router = APIRouter()


@router.post("/alipay/notify", summary="支付宝异步通知回调")
async def alipay_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form_data = await request.form()
    success = await handle_alipay_notify(dict(form_data), db)
    if success:
        return PlainTextResponse("success")
    return PlainTextResponse("fail", status_code=400)


@router.post("/alipay/return/{order_id}", response_model=PaymentOrderOut, summary="支付宝同步回跳确认")
async def alipay_return(
    order_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    return await confirm_alipay_return_public(order_id, data, db)


@router.post("/alipay/sync/{order_id}", response_model=PaymentOrderOut, summary="支付宝订单查单同步")
async def alipay_sync(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    return await sync_alipay_order_public(order_id, db)
