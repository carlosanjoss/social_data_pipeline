from celery import Celery
from celery.signals import task_failure, task_retry

app = Celery("radar_odio")
app.config_from_object("tasks.config")

# Auto-discover tasks in all tasks.* modules
app.autodiscover_tasks(["tasks.ingest", "tasks.validate", "tasks.load", "tasks.pipeline"])


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """After max retries exceeded, persist failed task to MongoDB dead-letter collection."""
    from tasks.dead_letter import record_dead_letter
    record_dead_letter(
        task_name=sender.name,
        task_id=task_id,
        args=list(args),
        kwargs=kwargs,
        exception=repr(exception),
        traceback=str(einfo),
    )


@task_retry.connect
def on_task_retry(sender, request, reason, einfo, **kw):
    from config import get_logger
    logger = get_logger("tasks.retry")
    logger.warning(
        "task_retry",
        task=sender.name,
        task_id=request.id,
        retries=request.retries,
        reason=str(reason),
    )
