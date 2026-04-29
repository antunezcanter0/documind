#!/usr/bin/env python3
# celery_worker.py
import os
import sys
from pathlib import Path

# Agregar el directorio del proyecto al PYTHONPATH
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configurar variable de entorno para el módulo de Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.celery_app")

from app.core.celery_app import celery_app

if __name__ == "__main__":
    # Iniciar worker con configuración específica
    celery_app.start([
        "worker",
        "--loglevel=info",
        "--queues=document_processing,embedding_tasks,maintenance",
        "--concurrency=4",
        "--prefetch-multiplier=1",
        "--max-tasks-per-child=1000",
        "--time-limit=300",  # 5 minutos por task
        "--soft-time-limit=240",  # 4 minutos soft limit
    ])
