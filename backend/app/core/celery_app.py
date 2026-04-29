# app/core/celery_app.py
import os
from celery import Celery
from app.core.config import settings
from app.core.ai_logger import ai_logger

# Configuración de Celery
celery_app = Celery(
    "documind",
    broker=settings.REDIS_CONNECTION_STRING,
    backend=settings.REDIS_CONNECTION_STRING,
    include=[
        "app.tasks.document_processing",
        "app.tasks.embedding_tasks",
        "app.tasks.maintenance_tasks"
    ]
)

# Configuración de Celery
celery_app.conf.update(
    # Broker settings
    broker_url=settings.REDIS_CONNECTION_STRING,
    result_backend=settings.REDIS_CONNECTION_STRING,
    
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task routing
    task_routes={
        "app.tasks.document_processing.*": {"queue": "document_processing"},
        "app.tasks.embedding_tasks.*": {"queue": "embedding_tasks"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
    
    # Task priorities
    task_default_priority=5,
    worker_direct=True,
    
    # Result expiration
    result_expires=3600,  # 1 hour
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Configuración de queues
celery_app.conf.task_queues = {
    "document_processing": {
        "exchange": "document_processing",
        "routing_key": "document_processing",
    },
    "embedding_tasks": {
        "exchange": "embedding_tasks", 
        "routing_key": "embedding_tasks",
    },
    "maintenance": {
        "exchange": "maintenance",
        "routing_key": "maintenance",
    },
}

# Configuración de schedules para tareas periódicas
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Cleanup de resultados antiguos cada 6 horas
    "cleanup-old-results": {
        "task": "app.tasks.maintenance_tasks.cleanup_old_results",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    
    # Health check de workers cada 5 minutos
    "worker-health-check": {
        "task": "app.tasks.maintenance_tasks.worker_health_check",
        "schedule": crontab(minute="*/5"),
    },
    
    # Cache cleanup cada 2 horas
    "cache-cleanup": {
        "task": "app.tasks.maintenance_tasks.cache_cleanup",
        "schedule": crontab(minute=0, hour="*/2"),
    },
}

@celery_app.task(bind=True)
def debug_task(self):
    """Task de debugging para Celery"""
    ai_logger.logger.info(f"Debug task executed: {self.request.id}")
    return f"Debug task executed: {self.request.id}"

# Event handlers para logging
@celery_app.task(after_configure=True)
def setup_logging(sender, **kwargs):
    """Configurar logging para Celery"""
    import logging
    logging.basicConfig(level=logging.INFO)
    ai_logger.logger.info("Celery logging configured")

# Event handlers para monitoreo
@celery_app.event.setup
def event_setup(**kwargs):
    """Setup de eventos de Celery"""
    ai_logger.logger.info("Celery event monitoring enabled")

@celery_app.event.task_prerun
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handler antes de ejecutar tarea"""
    ai_logger.logger.info(f"Task starting: {task.name}[{task_id}] with args: {len(args) if args else 0}")

@celery_app.event.task_postrun
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Handler después de ejecutar tarea"""
    ai_logger.logger.info(f"Task completed: {task.name}[{task_id}] with state: {state}")

@celery_app.event.task_failure
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, **kwds):
    """Handler para fallos de tareas"""
    ai_logger.logger.error(f"Task failed: {task_id} - {exception}")

@celery_app.event.task_success
def task_success_handler(sender=None, result=None, **kwargs):
    """Handler para tareas exitosas"""
    ai_logger.logger.info(f"Task success: {result}")

if __name__ == "__main__":
    celery_app.start()
