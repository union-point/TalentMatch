from celery import Celery

from app.config import settings

celery_app = Celery(
    "talent_match",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


celery_app.autodiscover_tasks(["app.tasks"], related_name="deep_analysis_tasks")

celery_app.conf.update(
    include=["app.tasks.auth_tasks"],
    beat_schedule={
        "deliver-auth-email": {"task": "tasks.deliver_auth_email", "schedule": 15.0},
        "cleanup-identity": {"task": "tasks.cleanup_identity", "schedule": 3600.0},
        "recover-expired-deep-analyses": {
            "task": "tasks.recover_expired_deep_analyses",
            "schedule": 30.0,
        },
        "dispatch-pending-deep-analyses": {
            "task": "tasks.dispatch_pending_deep_analyses",
            "schedule": 30.0,
        },
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
