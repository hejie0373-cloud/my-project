"""
全局配置。

默认值面向本地开发环境，部署环境通过 .env 覆盖。
"""
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置。"""

    # 数据库
    DB_URL: str = "mysql+aiomysql://root:root123@localhost:3306/keliudb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Elasticsearch
    ES_URL: str = "http://localhost:9200"

    # JWT
    SECRET_KEY: str = "keliu-dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI 服务；未配置时使用本地规则或模板兜底
    DIFY_API_URL: str = "http://localhost"
    DIFY_CHURN_API_KEY: str = ""
    DIFY_COPY_API_KEY: str = ""
    DIFY_INSIGHT_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    # 阿里云短信；未配置时开发环境返回 mock 验证码
    ALIYUN_SMS_ACCESS_KEY_ID: str = ""
    ALIYUN_SMS_ACCESS_KEY_SECRET: str = ""
    ALIYUN_SMS_SIGN_NAME: str = ""
    ALIYUN_SMS_TEMPLATE_CODE: str = ""
    ALIYUN_SMS_VALID_TIME: int = 300

    # 环境
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # 开发便利开关。生产使用 Alembic，不建议自动建表。
    AUTO_CREATE_TABLES: bool = False

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # 限流
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_PERIOD: int = 60

    # 二维码登录确认页地址
    QR_CONFIRM_BASE_URL: str = "http://localhost:5173"

    # 微信测试号扫码登录
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_REDIRECT_URI: str = ""

    # 支付宝沙箱支付
    ALIPAY_APP_ID: str = ""
    ALIPAY_APP_PRIVATE_KEY: str = ""
    ALIPAY_ALIPAY_PUBLIC_KEY: str = ""
    ALIPAY_SELLER_ID: str = ""
    ALIPAY_GATEWAY: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    ALIPAY_NOTIFY_URL: str = ""
    ALIPAY_RETURN_URL: str = "http://localhost:5173/billing"
    ALIPAY_SIGN_TYPE: str = "RSA2"

    model_config = {
        "env_file": str(BACKEND_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
