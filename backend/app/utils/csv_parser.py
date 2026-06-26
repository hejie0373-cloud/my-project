"""
CSV 文件解析与字段校验工具
支持多格式日期识别、手机号脱敏、必填字段校验
"""
import re
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 日期格式列表（按优先级尝试）
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
]

# 必填字段
REQUIRED_FIELDS = ["name", "phone"]

# 可选字段及其默认值
OPTIONAL_FIELDS = {
    "email": None,
    "gender": "unknown",
    "birthday": None,
    "address": None,
    "preferred_contact": "sms",
    "visited_at": None,
    "service_type": None,
    "amount": None,
    "payment_method": None,
    "feedback": None,
}


def parse_date(value: Any) -> Optional[date]:
    """
    多格式日期解析
    支持：2024-01-15, 2024/01/15, 01/15/2024, 2024-01-15 10:30:00
    返回 date 对象或 None
    """
    if value is None:
        return None

    s = str(value).strip()
    if not s:
        return None

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date()
        except ValueError:
            continue

    return None


def parse_amount(value: Any) -> Optional[float]:
    """解析金额"""
    if value is None:
        return None
    try:
        s = str(value).strip().replace(",", "").replace("￥", "").replace("¥", "")
        if not s:
            return None
        return round(float(s), 2)
    except (ValueError, TypeError):
        return None


def validate_phone(phone: str) -> bool:
    """校验中国手机号格式"""
    return bool(re.match(r"^1[3-9]\d{9}$", str(phone).strip()))


def mask_phone(phone: str) -> str:
    """手机号脱敏：138****8000"""
    s = str(phone).strip()
    if len(s) >= 7:
        return s[:3] + "****" + s[-4:]
    return s


def validate_gender(value: Any) -> str:
    """校验并标准化性别"""
    if value is None:
        return "unknown"
    s = str(value).strip().lower()
    if s in ("男", "male", "m"):
        return "male"
    if s in ("女", "female", "f"):
        return "female"
    return "unknown"


def validate_preferred_contact(value: Any) -> str:
    """校验联系方式"""
    if value is None:
        return "sms"
    s = str(value).strip().lower()
    if s in ("email", "邮件", "邮箱"):
        return "email"
    if s in ("wechat", "微信", "weixin"):
        return "wechat"
    if s in ("sms", "短信", "手机"):
        return "sms"
    return "sms"


def clean_row(
    row: dict,
    existing_phones: set,
    csv_phones_seen: set,
    row_num: int,
) -> Tuple[Optional[dict], List[dict]]:
    """
    Silver 层清洗：逐行校验 + 标准化

    参数:
        row: 原始行数据
        existing_phones: DB 中已有的手机号集合
        csv_phones_seen: 当前 CSV 中已处理的手机号集合
        row_num: 行号（用于错误报告）

    返回:
        (cleaned_row, errors)
        - cleaned_row: 清洗后的数据，校验失败为 None
        - errors: 错误列表 [{row, field, reason}, ...]
    """
    errors = []
    cleaned = {}

    # 1. 必填字段检查
    for field in REQUIRED_FIELDS:
        value = row.get(field)
        if value is None or str(value).strip() == "":
            errors.append({
                "row": row_num,
                "field": field,
                "reason": f"{field} 为必填字段",
            })
            return None, errors

    # 2. 姓名
    name = str(row.get("name", "")).strip()
    if len(name) < 1 or len(name) > 100:
        errors.append({
            "row": row_num,
            "field": "name",
            "reason": f"姓名长度需在 1-100 之间，当前: {len(name)}",
        })
        return None, errors
    cleaned["name"] = name

    # 3. 手机号
    phone = str(row.get("phone", "")).strip()
    if not validate_phone(phone):
        errors.append({
            "row": row_num,
            "field": "phone",
            "reason": f"手机号格式不正确: {mask_phone(phone)}",
        })
        return None, errors

    # 重复检查
    if phone in existing_phones:
        errors.append({
            "row": row_num,
            "field": "phone",
            "reason": f"手机号 {mask_phone(phone)} 已存在于系统中",
        })
        return None, errors
    if phone in csv_phones_seen:
        errors.append({
            "row": row_num,
            "field": "phone",
            "reason": f"手机号 {mask_phone(phone)} 在 CSV 中重复",
        })
        return None, errors

    csv_phones_seen.add(phone)
    cleaned["phone"] = phone

    # 4. 邮箱
    email = row.get("email")
    if email is not None:
        email = str(email).strip()
        if email and "@" not in email:
            errors.append({
                "row": row_num,
                "field": "email",
                "reason": f"邮箱格式不正确: {email}",
            })
            return None, errors
        cleaned["email"] = email if email else None
    else:
        cleaned["email"] = None

    # 5. 性别
    cleaned["gender"] = validate_gender(row.get("gender"))

    # 6. 生日
    cleaned["birthday"] = parse_date(row.get("birthday"))

    # 7. 地址
    address = row.get("address")
    cleaned["address"] = str(address).strip() if address else None

    # 8. 首选联系方式
    cleaned["preferred_contact"] = validate_preferred_contact(row.get("preferred_contact"))

    # 9. 到店记录字段（可选）
    visited_at = parse_date(row.get("visited_at"))
    if visited_at:
        cleaned["visited_at"] = datetime.combine(visited_at, datetime.min.time())
    else:
        cleaned["visited_at"] = None

    service_type = row.get("service_type")
    cleaned["service_type"] = str(service_type).strip() if service_type else None

    cleaned["amount"] = parse_amount(row.get("amount"))

    payment_method = row.get("payment_method")
    cleaned["payment_method"] = str(payment_method).strip() if payment_method else None

    feedback = row.get("feedback")
    cleaned["feedback"] = str(feedback).strip() if feedback else None

    return cleaned, errors
