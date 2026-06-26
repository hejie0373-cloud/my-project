"""
Celery 应用配置
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "keliu",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 单个任务最长 30 分钟
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=200,
)

# 定时任务配置
celery_app.conf.beat_schedule = {
    "batch-score-all-customers": {
        "task": "app.tasks.scoring_task.batch_score_all_customers",
        "schedule": 2 * 60 * 60,  # 每 2 小时（TODO: 改为每天凌晨 02:00 cron）
        "options": {"expires": 3600},
    },
    "dispatch-due-campaigns": {
        "task": "app.tasks.campaign_task.dispatch_due_campaigns",
        "schedule": 60,
        "options": {"expires": 55},
    },
}

# 自动发现任务模块
celery_app.autodiscover_tasks([
    "app.tasks.import_task",
    "app.tasks.scoring_task",
    "app.tasks.campaign_task",
    "app.tasks.report_task",
])

# Explicit imports keep tasks registered in Docker workers even when autodiscovery
# does not import modules named outside the conventional "tasks.py" pattern.
import app.tasks.import_task  # noqa: E402,F401
import app.tasks.scoring_task  # noqa: E402,F401
import app.tasks.campaign_task  # noqa: E402,F401
import app.tasks.report_task  # noqa: E402,F401
