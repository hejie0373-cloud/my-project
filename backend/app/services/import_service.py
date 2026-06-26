"""CSV 批量导入服务，导入进度存储在 Redis。"""
import logging
import os
import uuid

import pandas as pd

from app.utils.csv_parser import clean_row
from app.utils.es_client import sync_customer_to_es
from app.utils.redis_client import get_import_progress as redis_get_progress
from app.utils.redis_client import set_import_progress

logger = logging.getLogger(__name__)


def _open_session(db_session_factory):
    session_or_factory = db_session_factory()
    if hasattr(session_or_factory, "begin") and not hasattr(session_or_factory, "execute"):
        return session_or_factory()
    return session_or_factory


async def create_import_task() -> str:
    """创建导入任务并初始化进度。"""
    task_id = uuid.uuid4().hex[:16]
    progress = {
        "task_id": task_id,
        "total": 0,
        "success": 0,
        "failed": 0,
        "status": "processing",
        "errors": [],
    }
    await set_import_progress(task_id, progress)
    return task_id


async def get_progress(task_id: str) -> dict:
    """查询导入进度。"""
    progress = await redis_get_progress(task_id)
    if progress:
        return progress
    return {
        "task_id": task_id,
        "total": 0,
        "success": 0,
        "failed": 0,
        "status": "not_found",
        "errors": [],
    }


async def process_csv_import(
    task_id: str,
    file_path: str,
    store_id: str,
    db_session_factory,
) -> dict:
    """处理 CSV 导入：清洗、校验、入库、同步搜索索引。"""
    progress = await redis_get_progress(task_id)
    if not progress:
        return {"error": "task not found"}

    try:
        df = pd.read_csv(file_path)
        total_rows = len(df)
        progress["total"] = total_rows
        await set_import_progress(task_id, progress)
        logger.info("[Import %s] read %s rows", task_id, total_rows)

        raw_rows = df.to_dict(orient="records")

        from app.models.customer import Customer
        from sqlalchemy import select

        async with _open_session(db_session_factory) as db:
            result = await db.execute(
                select(Customer.phone).where(
                    Customer.store_id == store_id,
                    Customer.is_deleted == False,  # noqa: E712
                )
            )
            existing_phones = {row[0] for row in result.all()}

        csv_phones_seen = set()
        cleaned_rows = []
        errors = []

        for index, row in enumerate(raw_rows, start=1):
            normalized = {
                key.strip().lower().replace(" ", "_"): value
                for key, value in row.items()
                if isinstance(key, str)
            }
            cleaned, row_errors = clean_row(normalized, existing_phones, csv_phones_seen, index)
            if cleaned:
                cleaned_rows.append(cleaned)
            if row_errors:
                errors.extend(row_errors)

        progress["failed"] = len(errors)
        progress["success"] = len(cleaned_rows)
        await set_import_progress(task_id, progress)
        logger.info("[Import %s] cleaned=%s errors=%s", task_id, len(cleaned_rows), len(errors))

        if cleaned_rows:
            from app.models.customer import Customer as CustomerModel, Visit

            async with _open_session(db_session_factory) as db:
                customer_row_pairs = []
                for row in cleaned_rows:
                    customer = CustomerModel(
                        store_id=store_id,
                        name=row["name"],
                        phone=row["phone"],
                        email=row.get("email"),
                        gender=row.get("gender", "unknown"),
                        birthday=row.get("birthday"),
                        address=row.get("address"),
                        preferred_contact=row.get("preferred_contact", "sms"),
                    )
                    customer_row_pairs.append((customer, row))
                customers_to_insert = [customer for customer, _ in customer_row_pairs]
                db.add_all(customers_to_insert)
                await db.commit()

                score_customer_ids = []
                for customer, row in customer_row_pairs:
                    await db.refresh(customer)
                    sync_customer_to_es(
                        customer_id=customer.id,
                        name=customer.name,
                        phone=customer.phone,
                        store_id=customer.store_id,
                    )
                    if row.get("visited_at") and row.get("service_type"):
                        db.add(Visit(
                            customer_id=customer.id,
                            store_id=store_id,
                            visited_at=row["visited_at"],
                            service_type=row["service_type"],
                            amount=row.get("amount") or 0,
                            payment_method=row.get("payment_method"),
                            feedback=row.get("feedback"),
                            source="csv",
                        ))
                        score_customer_ids.append(customer.id)

                if score_customer_ids:
                    await db.commit()
                    try:
                        from app.tasks.scoring_task import recalculate_for_customer
                        for customer_id in score_customer_ids:
                            recalculate_for_customer.delay(customer_id)
                    except Exception as exc:
                        logger.warning("[Import %s] scoring trigger failed: %s", task_id, exc)

        progress["status"] = "done"
        progress["errors"] = errors
        await set_import_progress(task_id, progress)
        logger.info("[Import %s] done", task_id)

    except Exception as exc:
        logger.exception("[Import %s] failed", task_id)
        progress["status"] = "error"
        progress["errors"].append({"row": 0, "field": "system", "reason": str(exc)})
        await set_import_progress(task_id, progress)

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    return progress
