"""
CSV 导入 Celery 任务
"""
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def process_csv(self, task_id: str, file_path: str, store_id: str):
    """
    异步处理 CSV 导入

    参数:
        task_id: 导入任务 ID
        file_path: CSV 临时文件路径
        store_id: 店铺 ID
    """
    import asyncio
    from app.services.import_service import process_csv_import
    from app.db.session import get_session_factory

    logger.info(f"Celery 任务开始: task_id={task_id}, store={store_id}")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        process_csv_import(
            task_id=task_id,
            file_path=file_path,
            store_id=store_id,
            db_session_factory=get_session_factory,
        )
    )

    logger.info(f"Celery 任务完成: task_id={task_id}, status={result.get('status')}")
    return result
