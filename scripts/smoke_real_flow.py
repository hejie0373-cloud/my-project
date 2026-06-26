"""Run the real customer-to-campaign smoke flow through HTTP APIs.

Required:
    KELIU_ACCESS_TOKEN=<jwt>

Or, for an existing test account:
    KELIU_PHONE=13800000000
    KELIU_PASSWORD=your-password

Optional:
    KELIU_API_BASE=http://localhost:8009
    KELIU_TEST_PHONE=13900001234
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = os.getenv("KELIU_API_BASE", "http://localhost:8009").rstrip("/")
TOKEN = os.getenv("KELIU_ACCESS_TOKEN", "")
PHONE = os.getenv("KELIU_PHONE", "")
PASSWORD = os.getenv("KELIU_PASSWORD", "")


class SmokeError(RuntimeError):
    pass


def request_json(method: str, path: str, *, token: str = "", body: dict | None = None, query: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeError(f"{method} {path} -> {exc}") from exc


def request_multipart(path: str, *, token: str, field_name: str, filename: str, content: str) -> dict:
    boundary = f"----keliu-smoke-{uuid.uuid4().hex}"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        "Content-Type: text/csv; charset=utf-8\r\n\r\n".encode()
    )
    body.write(content.encode("utf-8-sig"))
    body.write(f"\r\n--{boundary}--\r\n".encode())
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = Request(f"{API_BASE}{path}", data=body.getvalue(), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"POST {path} -> HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeError(f"POST {path} -> {exc}") from exc


def login() -> str:
    if TOKEN:
        return TOKEN
    if not PHONE or not PASSWORD:
        raise SmokeError("Set KELIU_ACCESS_TOKEN, or set KELIU_PHONE and KELIU_PASSWORD for an existing test account.")
    data = request_json("POST", "/auth/login/password", body={"phone": PHONE, "password": PASSWORD})
    token = data.get("access_token")
    if not token:
        raise SmokeError("Password login succeeded but access_token was missing.")
    return token


def ensure_store(token: str) -> None:
    me = request_json("GET", "/users/me", token=token)
    if me.get("store_id"):
        return
    suffix = uuid.uuid4().hex[:6]
    request_json(
        "POST",
        "/stores",
        token=token,
        body={"name": f"Smoke Test Store {suffix}", "address": "Smoke Test", "industryType": "retail"},
    )


def make_csv() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    phone = os.getenv("KELIU_TEST_PHONE", f"139{str(int(time.time()))[-8:]}")
    rows = [
        {
            "name": f"Smoke客户{suffix}",
            "phone": phone,
            "email": f"smoke-{suffix}@example.com",
            "gender": "unknown",
            "preferred_contact": "sms",
            "visited_at": (datetime.now(timezone.utc) - timedelta(days=45)).replace(microsecond=0).isoformat(),
            "service_type": "到店体验",
            "amount": "199.00",
            "payment_method": "cash",
            "feedback": "smoke flow",
        }
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue(), phone


def wait_import(token: str, task_id: str) -> dict:
    for _ in range(30):
        progress = request_json("GET", f"/customers/import/{task_id}", token=token)
        if progress.get("status") in {"done", "error"}:
            return progress
        time.sleep(1)
    raise SmokeError(f"Import task {task_id} did not finish within 30 seconds.")


def find_customer(token: str, phone: str) -> dict:
    result = request_json("GET", "/customers", token=token, query={"search": phone, "page": 1, "page_size": 20})
    for item in result.get("items", []):
        if item.get("phone") == phone:
            return item
    raise SmokeError(f"Imported customer with phone {phone} was not found.")


def run() -> None:
    print(f"API base: {API_BASE}")
    token = login()
    print("1. authenticated")

    ensure_store(token)
    print("2. store ready")

    csv_content, imported_phone = make_csv()
    import_result = request_multipart("/customers/import", token=token, field_name="file", filename="customers.csv", content=csv_content)
    task_id = import_result.get("task_id")
    if not task_id:
        raise SmokeError("Import response did not include task_id.")
    progress = wait_import(token, task_id)
    if progress.get("status") != "done" or progress.get("success", 0) < 1:
        raise SmokeError(f"Import did not succeed: {progress}")
    print("3. imported customer with visit")

    customer = find_customer(token, imported_phone)
    customer_id = customer["id"]
    visit_body = {
        "visited_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "service_type": "复购体验",
        "staff_name": "Smoke",
        "amount": 299.0,
        "payment_method": "card",
        "feedback": "second visit",
    }
    request_json("POST", f"/customers/{customer_id}/visits", token=token, body=visit_body)
    print("4. recorded visit")

    score = request_json("POST", f"/metrics/churn/{customer_id}", token=token)
    if "churn_score" not in score:
        raise SmokeError(f"AI score response missing churn_score: {score}")
    print("5. AI score created")

    scheduled_at = (datetime.utcnow() + timedelta(minutes=2)).replace(microsecond=0).isoformat()
    campaign = request_json(
        "POST",
        "/campaigns",
        token=token,
        body={
            "name": f"Smoke预约活动 {uuid.uuid4().hex[:6]}",
            "template": "{{客户姓名}}，感谢到店，欢迎本周再来体验{{服务项目}}。",
            "channels": ["sms"],
            "scheduled_at": scheduled_at,
            "target_customer_ids": [customer_id],
        },
    )
    campaign_id = campaign.get("id")
    if not campaign_id:
        raise SmokeError(f"Campaign response missing id: {campaign}")
    print("6. scheduled campaign created")

    campaign_detail = request_json("GET", f"/campaigns/{campaign_id}", token=token)
    logs = request_json("GET", f"/campaigns/{campaign_id}/logs", token=token)
    dashboard = request_json("GET", "/analytics/dashboard", token=token)
    if logs.get("total", 0) < 1:
        raise SmokeError(f"Campaign logs were not created: {logs}")
    print("7. stats checked")

    summary = {
        "customer_id": customer_id,
        "campaign_id": campaign_id,
        "campaign_status": campaign_detail.get("status"),
        "campaign_logs": logs.get("total"),
        "dashboard_keys": sorted(dashboard.keys()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        run()
    except SmokeError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
