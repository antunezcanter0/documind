#!/usr/bin/env python3
# celery_beat.py
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
    # Iniciar scheduler para tareas periódicas
    celery_app.start([
        "beat",
        "--loglevel=info",
        "--pidfile=/tmp/celerybeat.pid",
        "--schedule=/tmp/celerybeat-schedule",
    ])
