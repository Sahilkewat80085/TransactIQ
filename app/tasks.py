from celery import Celery
from app.config import settings

celery_app = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_track_started=True,
    timezone='UTC',
)

@celery_app.task(name="app.tasks.process_csv_task")
def process_csv_task(job_id_str: str):
    # This is import-deferred to avoid circular imports
    from app.services.pipeline import run_pipeline
    run_pipeline(job_id_str)
