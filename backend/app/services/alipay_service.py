"""支付宝沙箱支付服务。"""
import base64
from datetime import datetime
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from fastapi import HTTPException, status
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config import settings


def create_page_pay_url(
    order_no: str,
    amount_cents: int,
    subject: str,
    body: str = "",
    return_url: str | None = None,
) -> str:
    """生成支付宝电脑网站支付 URL。"""
    _ensure_alipay_config()
    biz_content = {
        "out_trade_no": order_no,
        "product_code": "FAST_INSTANT_TRADE_PAY",
        "total_amount": f"{amount_cents / 100:.2f}",
        "subject": subject,
        "body": body or subject,
    }
    if settings.ALIPAY_SELLER_ID:
        biz_content["seller_id"] = settings.ALIPAY_SELLER_ID
    params = _base_params("alipay.trade.page.pay")
    params.update({
        "return_url": return_url or settings.ALIPAY_RETURN_URL,
        "notify_url": settings.ALIPAY_NOTIFY_URL,
        "biz_content": _json_dumps(biz_content),
    })
    params["sign"] = _sign(params)
    return f"{settings.ALIPAY_GATEWAY}?{urlencode(params, quote_via=quote_plus)}"


async def query_trade(order_no: str) -> dict | None:
    """Query Alipay for an order's latest trade state."""
    import httpx

    _ensure_alipay_config()
    params = _base_params("alipay.trade.query")
    params["biz_content"] = _json_dumps({"out_trade_no": order_no})
    params["sign"] = _sign(params)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.ALIPAY_GATEWAY, data=params)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    return payload.get("alipay_trade_query_response")


def verify_notify(data: dict) -> bool:
    """验证支付宝异步通知签名。"""
    return _verify_signed_data(data, require_seller_id=True)


def verify_return(data: dict) -> bool:
    """Verify Alipay's browser return params."""
    signed_data = {k: v for k, v in data.items() if k not in {"order_id", "payment"}}
    return _verify_signed_data(signed_data, require_seller_id=False)


def _verify_signed_data(data: dict, require_seller_id: bool) -> bool:
    if not settings.ALIPAY_ALIPAY_PUBLIC_KEY:
        return False
    if data.get("app_id") != settings.ALIPAY_APP_ID:
        return False
    seller_id = data.get("seller_id")
    if settings.ALIPAY_SELLER_ID and (seller_id or require_seller_id):
        if seller_id != settings.ALIPAY_SELLER_ID:
            return False
    if data.get("sign_type") and data.get("sign_type") != settings.ALIPAY_SIGN_TYPE:
        return False
    signature = data.get("sign")
    if not signature:
        return False
    unsigned = {k: v for k, v in data.items() if k not in {"sign", "sign_type"}}
    content = _content_to_sign(unsigned)
    public_key = _load_public_key(settings.ALIPAY_ALIPAY_PUBLIC_KEY)
    try:
        public_key.verify(
            base64.b64decode(signature),
            content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def _base_params(method: str) -> dict:
    return {
        "app_id": settings.ALIPAY_APP_ID,
        "method": method,
        "charset": "utf-8",
        "sign_type": settings.ALIPAY_SIGN_TYPE,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "format": "JSON",
    }


def _json_dumps(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build_return_url(order_id: str) -> str:
    """Build an Alipay result URL independent of the current merchant session."""
    parsed = urlparse(settings.ALIPAY_RETURN_URL)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"order_id": order_id, "payment": "alipay"})
    return urlunparse(parsed._replace(path="/payment/alipay/result", query=urlencode(query)))


def _content_to_sign(params: dict) -> str:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    return "&".join(f"{key}={clean[key]}" for key in sorted(clean))


def _sign(params: dict) -> str:
    private_key = _load_private_key(settings.ALIPAY_APP_PRIVATE_KEY)
    signature = private_key.sign(
        _content_to_sign(params).encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def _normalize_key(raw_key: str) -> str:
    return raw_key.replace("\\n", "\n").strip()


def _load_private_key(raw_key: str):
    normalized = _normalize_key(raw_key)
    try:
        return serialization.load_pem_private_key(normalized.encode("utf-8"), password=None)
    except ValueError:
        if "BEGIN RSA PRIVATE KEY" in normalized:
            # Some Alipay tools export PKCS#8 content with an RSA PRIVATE KEY header.
            pkcs8 = normalized.replace("BEGIN RSA PRIVATE KEY", "BEGIN PRIVATE KEY").replace(
                "END RSA PRIVATE KEY",
                "END PRIVATE KEY",
            )
        else:
            # Some Alipay tools export PKCS#8 content without a PEM header.
            pkcs8 = f"-----BEGIN PRIVATE KEY-----\n{normalized}\n-----END PRIVATE KEY-----"
        return serialization.load_pem_private_key(pkcs8.encode("utf-8"), password=None)


def _load_public_key(raw_key: str):
    normalized = _normalize_key(raw_key)
    try:
        return serialization.load_pem_public_key(normalized.encode("utf-8"))
    except ValueError:
        if "BEGIN PUBLIC KEY" in normalized:
            raise
        pkcs8 = f"-----BEGIN PUBLIC KEY-----\n{normalized}\n-----END PUBLIC KEY-----"
        return serialization.load_pem_public_key(pkcs8.encode("utf-8"))


def _ensure_alipay_config() -> None:
    if not settings.ALIPAY_APP_ID or not settings.ALIPAY_APP_PRIVATE_KEY or not settings.ALIPAY_NOTIFY_URL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ALIPAY_CONFIG_MISSING",
        )
