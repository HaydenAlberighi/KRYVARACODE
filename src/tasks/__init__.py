from celery import Celery

from src.core.config import settings

# Initialize Celery application
# Using REDIS_URL from settings for both broker and backend
celery_app = Celery(
    "kryvara_tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL
)

# Configure Celery to handle JSON serialization for task results
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Remove timezone=settings.TIMEZONE as it's missing from Settings
    enable_utc=True,
)

__all__ = ["celery_app"]
