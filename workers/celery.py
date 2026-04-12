from celery import Celery

celery = Celery(
    "techit",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

@celery.task
def dummy_task():
    return "Celery worker is ready"

print("✅ Celery module loaded")
