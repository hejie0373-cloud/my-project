"""Check whether the real integration runtime is ready.

The script intentionally prints only presence/status, never secret values.
Run from the repository root:
    python scripts/check_runtime_env.py

Optional live checks:
    KELIU_CHECK_LIVE=1 python scripts/check_runtime_env.py
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV = ROOT / "backend" / ".env"
BACKEND_ENV_PROD = ROOT / "backend" / ".env.prod"

CORE_ENV_KEYS = ("DB_URL", "REDIS_URL", "ES_URL", "SECRET_KEY")
DIFY_KEYS = ("DIFY_API_URL", "DIFY_CHURN_API_KEY", "DIFY_COPY_API_KEY", "DIFY_INSIGHT_API_KEY")
ALIPAY_KEYS = (
    "ALIPAY_APP_ID",
    "ALIPAY_APP_PRIVATE_KEY",
    "ALIPAY_ALIPAY_PUBLIC_KEY",
    "ALIPAY_GATEWAY",
    "ALIPAY_NOTIFY_URL",
    "ALIPAY_RETURN_URL",
)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    current_key: str | None = None
    current_quote: str | None = None
    current_value: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if current_key:
            current_value.append(raw_line)
            if current_quote and raw_line.endswith(current_quote):
                values[current_key] = "\n".join(current_value).strip(current_quote)
                current_key = None
                current_quote = None
                current_value = []
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] in {'"', "'"} and not value.endswith(value[0]):
            current_key = key
            current_quote = value[0]
            current_value = [value.lstrip(current_quote)]
            continue
        values[key] = value.strip('"').strip("'")
    return values


def status_line(ok: bool, label: str, detail: str = "") -> tuple[bool, str]:
    mark = "OK" if ok else "MISSING"
    suffix = f" - {detail}" if detail else ""
    return ok, f"[{mark}] {label}{suffix}"


def warn_line(ok: bool, label: str, detail: str = "") -> tuple[bool, str]:
    mark = "OK" if ok else "WARN"
    suffix = f" - {detail}" if detail else ""
    return True, f"[{mark}] {label}{suffix}"


def host_port_from_url(value: str) -> tuple[str, int] | None:
    parsed = urlparse(value)
    if parsed.scheme.startswith("mysql"):
        host = parsed.hostname
        port = parsed.port or 3306
    elif parsed.scheme.startswith("redis"):
        host = parsed.hostname
        port = parsed.port or 6379
    elif parsed.scheme in {"http", "https"}:
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    else:
        return None
    if not host:
        return None
    return host, port


def tcp_check(name: str, value: str) -> tuple[bool, str]:
    target = host_port_from_url(value)
    if not target:
        return status_line(False, f"{name} live check", "cannot parse endpoint")
    host, port = target
    try:
        with socket.create_connection((host, port), timeout=3):
            return status_line(True, f"{name} live check", f"{host}:{port}")
    except OSError as exc:
        return status_line(False, f"{name} live check", f"{host}:{port} unreachable ({exc})")


def http_check(name: str, url: str) -> tuple[bool, str]:
    try:
        request = Request(url, method="GET")
        with urlopen(request, timeout=5) as response:
            ok = 200 <= response.status < 500
            return status_line(ok, name, f"HTTP {response.status}")
    except Exception as exc:
        return status_line(False, name, str(exc))


def compose_has_service(path: Path, service_name: str) -> bool:
    if not path.exists():
        return False
    needle = f"  {service_name}:"
    return needle in path.read_text(encoding="utf-8")


def check_env_file(path: Path, keys: tuple[str, ...], title: str) -> list[tuple[bool, str]]:
    env = load_env(path)
    rows = [status_line(path.exists(), title, str(path.relative_to(ROOT)) if path.exists() else "file not found")]
    for key in keys:
        rows.append(status_line(bool(env.get(key)), f"{title} {key}"))
    return rows


def main() -> int:
    rows: list[tuple[bool, str]] = []
    env = load_env(BACKEND_ENV)

    rows.extend(check_env_file(BACKEND_ENV, CORE_ENV_KEYS, "backend/.env core"))
    for key in DIFY_KEYS:
        rows.append(status_line(bool(env.get(key)), f"backend/.env {key}"))
    for key in ALIPAY_KEYS:
        rows.append(status_line(bool(env.get(key)), f"backend/.env {key}"))

    prod_env = load_env(BACKEND_ENV_PROD)
    rows.append(status_line(BACKEND_ENV_PROD.exists(), "backend/.env.prod", "template for docker-compose.prod.yml"))
    for key in (*CORE_ENV_KEYS, *DIFY_KEYS, *ALIPAY_KEYS):
        rows.append(warn_line(bool(prod_env.get(key)), f"backend/.env.prod {key}", "fill before production deploy" if not prod_env.get(key) else ""))

    rows.append(status_line(compose_has_service(ROOT / "docker-compose.yml", "celery_worker"), "docker-compose.yml celery_worker service"))
    rows.append(status_line(compose_has_service(ROOT / "docker-compose.yml", "celery_beat"), "docker-compose.yml celery_beat service"))
    rows.append(status_line(compose_has_service(ROOT / "docker-compose.prod.yml", "celery-worker"), "docker-compose.prod.yml celery-worker service"))
    rows.append(status_line(compose_has_service(ROOT / "docker-compose.prod.yml", "celery-beat"), "docker-compose.prod.yml celery-beat service"))

    if os.getenv("KELIU_CHECK_LIVE") == "1":
        for key in ("DB_URL", "REDIS_URL", "ES_URL"):
            value = env.get(key)
            if value:
                rows.append(tcp_check(key, value))
        api_base = os.getenv("KELIU_API_BASE", "http://127.0.0.1:8009").rstrip("/")
        rows.append(http_check("backend health", f"{api_base}/health"))

    for _, line in rows:
        print(line)

    required_failures = [
        line for ok, line in rows
        if not ok and (
            "backend/.env core" in line
            or "backend/.env DIFY_" in line
            or "backend/.env ALIPAY_" in line
            or "celery" in line
            or "live check" in line
            or "backend health" in line
        )
    ]
    if required_failures:
        print("\nRuntime is not fully ready. Fix the MISSING items above, then rerun.")
        return 1
    print("\nRuntime checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
