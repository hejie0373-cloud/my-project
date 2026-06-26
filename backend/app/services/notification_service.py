"""
消息通知服务：多渠道 Provider 抽象层

Provider 模式：
- 未配置凭据 → Mock 模式（日志打印）
- 已配置凭据 → 真实发送
- 任何 Provider 失败不影响其他渠道
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.integration import Integration

logger = logging.getLogger(__name__)


# ============================================================
# 抽象基类
# ============================================================

class BaseNotificationProvider(ABC):
    """通知 Provider 抽象基类"""

    @abstractmethod
    async def send(self, to: str, content: str) -> bool:
        """
        发送通知
        返回 True=成功, False=失败
        """
        ...

    @property
    @abstractmethod
    def channel(self) -> str:
        ...


# ============================================================
# 短信 Provider
# ============================================================

class SMSProvider(BaseNotificationProvider):
    """
    阿里云号码认证 - 短信认证 Provider（个人开发者免企业资质）

    使用阿里云「号码认证服务 (Dypnsapi)」→「短信认证」子产品，
    无需企业营业执照，个人实名认证即可使用。
    系统提供预置签名和验证码模板，开箱即用。
    """

    def __init__(self, credentials: Optional[dict] = None):
        self.credentials = credentials or {}
        self._configured = bool(
            settings.ALIYUN_SMS_ACCESS_KEY_ID
            and settings.ALIYUN_SMS_ACCESS_KEY_SECRET
        )
        # 从控制台获取的预置签名名称和模板 Code
        self._sign_name = settings.ALIYUN_SMS_SIGN_NAME or ""
        self._template_code = settings.ALIYUN_SMS_TEMPLATE_CODE or ""
        self._valid_time = settings.ALIYUN_SMS_VALID_TIME

    @property
    def channel(self) -> str:
        return "sms"

    async def send(self, to: str, content: str) -> bool:
        """
        发送短信验证码
        - 未配置 → Mock 模式（日志打印）
        - 已配置 → 调用阿里云号码认证 API（SendSmsVerifyCode）
        """
        if not self._configured:
            logger.info(f"[MOCK SMS] to={to} content={content[:50]}...")
            return True

        return await self._send_aliyun_sms(to, content)

    async def _send_aliyun_sms(self, phone: str, code: str) -> bool:
        """
        调用阿里云号码认证 SendSmsVerifyCode API 发送验证码

        API 文档: https://api.aliyun.com/api/Dypnsapi/2017-05-25/SendSmsVerifyCode
        Python SDK: alibabacloud_dypnsapi20170525
        """
        from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        try:
            config = open_api_models.Config(
                access_key_id=settings.ALIYUN_SMS_ACCESS_KEY_ID,
                access_key_secret=settings.ALIYUN_SMS_ACCESS_KEY_SECRET,
            )
            config.endpoint = "dypnsapi.aliyuncs.com"
            client = DypnsapiClient(config)

            request = dypnsapi_models.SendSmsVerifyCodeRequest(
                phone_number=phone,
                sign_name=self._sign_name,
                template_code=self._template_code,
                template_param=f'{{"code":"{code}","min":"{self._valid_time // 60}"}}',
                valid_time=self._valid_time,    # 验证码有效期（秒）
                country_code="86",               # 中国大陆
                code_type=1,                     # 1=纯数字验证码
                return_verify_code=False,        # 不返回验证码（安全）
            )

            runtime = util_models.RuntimeOptions()
            resp = client.send_sms_verify_code_with_options(request, runtime)

            body = resp.body
            # 打印完整响应排查问题
            logger.info(f"[SMS] 完整响应 phone={phone} code={body.code} "
                        f"message={body.message} biz_id={getattr(body, 'biz_id', 'N/A')}")
            if body.code == "OK":
                logger.info(f"[SMS] 发送成功 phone={phone}")
                return True
            else:
                logger.error(
                    f"[SMS] 发送失败 phone={phone} "
                    f"code={body.code} message={body.message}"
                )
                return False

        except Exception as e:
            logger.error(f"[SMS] SDK 异常 phone={phone}: {e}")
            return False


# ============================================================
# 邮件 Provider
# ============================================================

class EmailProvider(BaseNotificationProvider):
    """邮件 Provider（SMTP/SendGrid，未配置时 Mock）"""

    def __init__(self, credentials: Optional[dict] = None):
        self.credentials = credentials
        self._configured = bool(
            credentials
            and credentials.get("smtp_host")
            and credentials.get("smtp_username")
        )

    @property
    def channel(self) -> str:
        return "email"

    async def send(self, to: str, content: str) -> bool:
        if not self._configured:
            logger.info(f"[MOCK EMAIL] to={to} content={content[:80]}...")
            return True

        # TODO: 接入 SMTP/SendGrid
        # import aiosmtplib
        # ...
        logger.info(f"[REAL EMAIL] to={to}")
        return True


# ============================================================
# 微信 Provider
# ============================================================

class WechatProvider(BaseNotificationProvider):
    """微信公众号模板消息 Provider（未配置时 Mock）"""

    def __init__(self, credentials: Optional[dict] = None):
        self.credentials = credentials
        self._configured = bool(
            credentials
            and credentials.get("app_id")
            and credentials.get("app_secret")
        )

    @property
    def channel(self) -> str:
        return "wechat"

    async def send(self, to: str, content: str) -> bool:
        if not self._configured:
            logger.info(f"[MOCK WECHAT] to={to} content={content[:50]}...")
            return True

        # TODO: 接入微信公众号模板消息 API
        # ...
        logger.info(f"[REAL WECHAT] to={to}")
        return True


# ============================================================
# Provider 工厂
# ============================================================

PROVIDER_MAP = {
    "sms": SMSProvider,
    "email": EmailProvider,
    "wechat": WechatProvider,
}


async def get_provider(
    channel: str, store_id: str, db: AsyncSession
) -> BaseNotificationProvider:
    """
    Provider 工厂函数

    1. 从 integrations 表查店铺凭据
    2. 有凭据 → 真实发送
    3. 无凭据 → Mock 模式（日志打印）
    """
    provider_cls = PROVIDER_MAP.get(channel)
    if not provider_cls:
        raise ValueError(f"不支持的渠道: {channel}")

    # 查集成凭据
    result = await db.execute(
        select(Integration).where(
            Integration.store_id == store_id,
            Integration.type == channel,
            Integration.enabled == True,  # noqa: E712
        )
    )
    integration = result.scalar_one_or_none()

    credentials = integration.credentials if integration else None
    return provider_cls(credentials)


async def send_to_customer(
    channel: str,
    to: str,
    content: str,
    store_id: str,
    db: AsyncSession,
) -> tuple[bool, str]:
    """
    向指定客户发送消息

    返回: (success, response_text)
    """
    provider = await get_provider(channel, store_id, db)
    try:
        success = await provider.send(to, content)
        response = "sent" if success else "failed"
        return success, response
    except Exception as e:
        logger.error(f"[{channel.upper()}] 发送失败: {e}")
        return False, str(e)
