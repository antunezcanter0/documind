# app/tasks/maintenance_tasks.py
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.celery_app import celery_app
from app.core.database import get_db
from app.core.ai_logger import ai_logger
from app.core.metrics import ai_metrics
from app.core.cache import cache_manager

@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_old_results")
def cleanup_old_results():
    """
    Task periódico para limpiar resultados antiguos de Celery
    """
    try:
        ai_logger.logger.info("Starting cleanup of old Celery results")
        
        # Limpiar resultados más antiguos de 24 horas
        from celery.result import AsyncResult
        from celery.backends.base import DisabledBackend
        
        # Obtener todos los task IDs de resultados
        inspect = celery_app.control.inspect()
        
        # Limpiar resultados expirados (Celery lo hace automáticamente con result_expires)
        cleaned_count = 0
        
        ai_metrics.increment_counter("maintenance_cleanup_runs")
        ai_logger.logger.info(f"Cleanup completed: {cleaned_count} results cleaned")
        
        return {
            'status': 'success',
            'cleaned_count': cleaned_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Cleanup failed: {str(e)}")
        ai_metrics.increment_counter("maintenance_cleanup_failed")
        raise

@celery_app.task(name="app.tasks.maintenance_tasks.worker_health_check")
def worker_health_check():
    """
    Task periódico para verificar salud de workers Celery
    """
    try:
        ai_logger.logger.info("Starting worker health check")
        
        # Obtener estadísticas de workers
        inspect = celery_app.control.inspect()
        
        # Stats activos
        stats = inspect.stats()
        
        # Workers activos
        active_workers = inspect.active()
        
        # Tasks actualmente ejecutándose
        active_tasks = []
        if active_workers:
            for worker_name, tasks in active_workers.items():
                for task in tasks:
                    active_tasks.append({
                        'worker': worker_name,
                        'task_id': task['id'],
                        'name': task['name'],
                        'time': task.get('time_start', 0)
                    })
        
        # Calcular métricas
        total_workers = len(stats) if stats else 0
        total_active_tasks = len(active_tasks)
        
        # Registrar métricas
        ai_metrics.set_gauge("celery_active_workers", total_workers)
        ai_metrics.set_gauge("celery_active_tasks", total_active_tasks)
        
        # Verificar health
        health_status = "healthy"
        if total_workers == 0:
            health_status = "unhealthy"
        elif total_active_tasks > 100:  # Threshold configurable
            health_status = "degraded"
        
        ai_logger.logger.info(f"Worker health check completed: {total_workers} workers, {total_active_tasks} active tasks")
        
        return {
            'status': 'success',
            'health': health_status,
            'workers': total_workers,
            'active_tasks': total_active_tasks,
            'worker_details': stats,
            'active_task_details': active_tasks,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Worker health check failed: {str(e)}")
        ai_metrics.increment_counter("worker_health_check_failed")
        raise

@celery_app.task(name="app.tasks.maintenance_tasks.cache_cleanup")
def cache_cleanup():
    """
    Task periódico para limpiar caché antiguo
    """
    try:
        ai_logger.logger.info("Starting cache cleanup")
        
        # Limpiar caché de embeddings expirados
        embedding_keys_deleted = cache_manager.clear_pattern("embedding:*")
        
        # Limpiar caché de RAG expirados (más agresivo)
        rag_keys_deleted = cache_manager.clear_pattern("rag:*")
        
        # Limpiar caché de LLM (menos agresivo)
        llm_keys_deleted = cache_manager.clear_pattern("llm:*")
        
        total_deleted = embedding_keys_deleted + rag_keys_deleted + llm_keys_deleted
        
        # Registrar métricas
        ai_metrics.increment_counter("cache_cleanup_runs")
        ai_metrics.record_histogram("cache_keys_deleted", total_deleted)
        
        ai_logger.logger.info(f"Cache cleanup completed: {total_deleted} keys deleted")
        
        return {
            'status': 'success',
            'embedding_keys_deleted': embedding_keys_deleted,
            'rag_keys_deleted': rag_keys_deleted,
            'llm_keys_deleted': llm_keys_deleted,
            'total_deleted': total_deleted,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Cache cleanup failed: {str(e)}")
        ai_metrics.increment_counter("cache_cleanup_failed")
        raise

@celery_app.task(name="app.tasks.maintenance_tasks.database_maintenance")
def database_maintenance():
    """
    Task para mantenimiento de base de datos
    """
    try:
        ai_logger.logger.info("Starting database maintenance")
        
        async def perform_maintenance():
            async for db in get_db():
                # Estadísticas de la base de datos
                from sqlalchemy import text, select, func
                from app.models.document import Document, DocumentChunk
                
                # Contar documentos y chunks
                doc_count_result = await db.execute(select(func.count(Document.id)))
                document_count = doc_count_result.scalar()
                
                chunk_count_result = await db.execute(select(func.count(DocumentChunk.id)))
                chunk_count = chunk_count_result.scalar()
                
                # Verificar integridad (chunks sin documentos)
                orphaned_chunks_result = await db.execute(
                    text("""
                    SELECT COUNT(dc.id) 
                    FROM document_chunks dc 
                    LEFT JOIN documents d ON dc.document_id = d.id 
                    WHERE d.id IS NULL
                    """)
                )
                orphaned_chunks = orphaned_chunks_result.scalar()
                
                # Limpiar chunks huérfanos si existen
                if orphaned_chunks > 0:
                    from sqlalchemy import delete
                    await db.execute(
                        delete(DocumentChunk).where(
                            DocumentChunk.document_id.not_in(
                                select(Document.id)
                            )
                        )
                    )
                    await db.commit()
                    ai_logger.logger.warning(f"Cleaned up {orphaned_chunks} orphaned chunks")
                
                return {
                    'document_count': document_count,
                    'chunk_count': chunk_count,
                    'orphaned_chunks_cleaned': orphaned_chunks
                }
        
        import asyncio
        stats = asyncio.run(perform_maintenance())
        
        # Registrar métricas
        ai_metrics.set_gauge("database_documents", stats['document_count'])
        ai_metrics.set_gauge("database_chunks", stats['chunk_count'])
        ai_metrics.increment_counter("database_maintenance_runs")
        
        ai_logger.logger.info(f"Database maintenance completed: {stats}")
        
        return {
            'status': 'success',
            **stats,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Database maintenance failed: {str(e)}")
        ai_metrics.increment_counter("database_maintenance_failed")
        raise

@celery_app.task(name="app.tasks.maintenance_tasks.metrics_report")
def metrics_report():
    """
    Task para generar reporte de métricas
    """
    try:
        ai_logger.logger.info("Generating metrics report")
        
        # Obtener métricas del sistema
        system_metrics = ai_metrics.get_all_metrics()
        
        # Obtener estadísticas del caché
        import asyncio
        cache_stats = asyncio.run(cache_manager.get_cache_stats())
        
        # Health check de workers
        inspect = celery_app.control.inspect()
        worker_stats = inspect.stats()
        
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'system_metrics': system_metrics,
            'cache_stats': cache_stats,
            'worker_count': len(worker_stats) if worker_stats else 0,
            'summary': {
                'total_requests': system_metrics['counters'].get('rag_operations_total', 0),
                'total_documents': system_metrics['counters'].get('document_processing_total', 0),
                'cache_hit_rate': cache_stats.get('hit_rate', 0),
                'active_models': len(system_metrics['model_metrics'])
            }
        }
        
        ai_logger.logger.info(f"Metrics report generated: {report['summary']}")
        
        return report
        
    except Exception as e:
        ai_logger.logger.error(f"Metrics report failed: {str(e)}")
        raise
