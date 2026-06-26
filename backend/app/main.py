"""
应用入口：FastAPI 实例化，注册路由、中间件、CORS、WebSocket、启动事件
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    from app.db.session import get_engine
    from app.db.base import Base  # noqa: F401 — 触发所有模型注册

    eng = get_engine()

    if settings.ENVIRONMENT == "development" and settings.AUTO_CREATE_TABLES:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表自动创建完成")

    try:
        from app.db.init_db import init_db
        async with eng.connect() as conn:
            await init_db(conn)
        logger.info("种子数据初始化完成")
    except Exception as e:
        logger.warning(f"种子数据初始化跳过: {e}")

    # 启动 Redis Pub/Sub 监听
    from app.websocket.handler import start_redis_listener
    asyncio.create_task(start_redis_listener())

    yield

    from app.utils.redis_client import close_redis
    await close_redis()
    await eng.dispose()
    logger.info("应用已关闭")


app = FastAPI(
    title="客留 API",
    version="1.0.0",
    description="AI 客户留存平台 — 后端 API",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流
from app.core.limiter import limiter  # noqa: E402

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"未处理的异常: {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "code": "INTERNAL_ERROR"},
    )


@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


# WebSocket
from app.websocket.handler import handle_connection  # noqa: E402

@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket, store_id: str, token: str = Query(...)):
    """WebSocket 实时通知端点 — URL: ws://host:8000/ws/{store_id}?token={access_token}"""
    await handle_connection(websocket, store_id, token)


# 路由注册
from app.routers.auth import router as auth_router  # noqa: E402
from app.routers.users import router as users_router  # noqa: E402
from app.routers.customers import router as customers_router  # noqa: E402
from app.routers.metrics import router as metrics_router  # noqa: E402
from app.routers.campaigns import router as campaigns_router  # noqa: E402
from app.routers.analytics import router as analytics_router  # noqa: E402
from app.routers.stores import router as stores_router  # noqa: E402
from app.routers.webhooks import router as webhooks_router  # noqa: E402
from app.routers.admin import router as admin_router  # noqa: E402
from app.routers.billing import router as billing_router  # noqa: E402
from app.routers.payment import router as payment_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["认证"])
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(users_router, prefix="/users", tags=["用户"])
app.include_router(stores_router, prefix="/stores", tags=["店铺"])
app.include_router(customers_router, prefix="/customers", tags=["客户"])
app.include_router(metrics_router, prefix="/metrics", tags=["AI 评分"])
app.include_router(campaigns_router, prefix="/campaigns", tags=["营销"])
app.include_router(analytics_router, prefix="/analytics", tags=["报表"])
app.include_router(billing_router, prefix="/billing", tags=["计费"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["CI/CD"])
app.include_router(admin_router, prefix="/admin", tags=["管理"])
app.include_router(payment_router, prefix="/payment", tags=["支付"])
app.include_router(payment_router, prefix="/api/payment", tags=["支付"])
