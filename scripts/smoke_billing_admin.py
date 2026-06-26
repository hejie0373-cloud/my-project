"""Smoke test billing and admin APIs against the real backend."""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


API_BASE = os.getenv("KELIU_API_BASE", "http://localhost:8009").rstrip("/")
MERCHANT_PHONE = os.getenv("KELIU_PHONE", "13800000001")
MERCHANT_PASSWORD = os.getenv("KELIU_PASSWORD", "keliu123456")
ADMIN_PHONE = os.getenv("KELIU_ADMIN_PHONE", "18626834206")
ADMIN_PASSWORD = os.getenv("KELIU_ADMIN_PASSWORD", "hejie123456")


class SmokeError(RuntimeError):
    pass


def request_json(method: str, path: str, *, token: str = "", body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeError(f"{method} {path} -> {exc}") from exc


def login(phone: str, password: str) -> str:
    data = request_json("POST", "/auth/login/password", body={"phone": phone, "password": password})
    token = data.get("access_token")
    if not token:
        raise SmokeError(f"Login succeeded but access_token was missing for {phone}.")
    return token


def run() -> None:
    print(f"API base: {API_BASE}")
    merchant_token = login(MERCHANT_PHONE, MERCHANT_PASSWORD)
    print("1. merchant authenticated")

    order = request_json("POST", "/billing/orders", token=merchant_token, body={"plan_name": "basic", "provider": "alipay"})
    checkout_url = order.get("checkout_url")
    if not checkout_url:
        raise SmokeError(f"Alipay order has no checkout_url: {order}")
    parsed = urlparse(checkout_url)
    if "alipay" not in parsed.netloc and "alipay" not in parsed.path:
        raise SmokeError(f"checkout_url does not look like Alipay: {checkout_url[:120]}")
    print("2. alipay sandbox order created")

    order_detail = request_json("GET", f"/billing/orders/{order['id']}", token=merchant_token)
    if order_detail.get("status") != "pending":
        raise SmokeError(f"Expected pending order, got: {order_detail}")
    print("3. merchant order query passed")

    admin_token = login(ADMIN_PHONE, ADMIN_PASSWORD)
    print("4. admin authenticated")

    admin_orders = request_json("GET", "/admin/payment-orders", token=admin_token)
    if admin_orders.get("total", 0) < 1:
        raise SmokeError(f"Admin payment orders were empty: {admin_orders}")
    summary = request_json("GET", "/admin/payment-summary", token=admin_token)
    stores = request_json("GET", "/admin/stores", token=admin_token)
    print("5. admin billing/stores query passed")

    print(json.dumps({
        "order_id": order["id"],
        "order_status": order_detail["status"],
        "checkout_host": parsed.netloc,
        "admin_order_total": admin_orders.get("total"),
        "summary_keys": sorted(summary.keys()),
        "store_total": stores.get("total"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        run()
    except SmokeError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
