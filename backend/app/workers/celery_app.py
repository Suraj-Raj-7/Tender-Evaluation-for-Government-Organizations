"""
backend/app/workers/celery_app.py
------------------------------------
Purpose: Creates the single Celery application instance. Both the
FastAPI routers (to queue a new background job) and the Celery worker
process (to know what tasks it's allowed to run) import this same
object -- it's the shared coordination point between the two.

Why this file exists: Celery can't function without one central "app"
that both the task-queuer and the task-runner agree on. This file
builds that app once, using Redis (already running via docker-compose)
as both the broker and the result backend.
"""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "tenderiq",
    # Broker: where a queued task waits until a worker is free to pick
    # it up. This is the "in line at the counter" part of the diagram.
    broker=settings.REDIS_URL,
    # Backend: where a task's status/result gets stored after it runs,
    # so something can later ask "is job X done, and what happened?"
    backend=settings.REDIS_URL,
    # Tells Celery which file contains the actual @celery_app.task
    # functions. tasks.py doesn't exist yet -- we build it next -- but
    # Celery only needs this path to resolve when a worker actually
    # starts, not right now when this file is just imported.
    include=["app.workers.tasks"],
)

# A few sane defaults: JSON is a safe, human-readable format for task
# arguments/results (vs. Celery's default pickle, which can execute
# arbitrary code if tampered with -- not something we want for a
# government platform). UTC keeps all timestamps unambiguous.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)