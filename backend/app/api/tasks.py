# app/api/tasks.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.core.celery_app import celery_app
from app.core.ai_logger import ai_logger
from app.tasks.document_processing import process_document_upload, delete_document_task, get_task_status
from app.tasks.embedding_tasks import generate_embeddings_batch, reindex_document_embeddings

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    result: Optional[Dict[str, Any]] = None
    info: Optional[Dict[str, Any]] = None
    progress: int = 0

class DocumentUploadRequest(BaseModel):
    file_path: str
    filename: str
    file_type: str
    metadata: Optional[Dict[str, Any]] = None

class BatchDocumentRequest(BaseModel):
    documents: List[DocumentUploadRequest]

class EmbeddingBatchRequest(BaseModel):
    texts: List[str]
    metadata: Optional[Dict[str, Any]] = None

@router.post("/upload-document", response_model=Dict[str, str])
async def upload_document_async(request: DocumentUploadRequest):
    """
    Iniciar procesamiento asíncrono de documento
    """
    try:
        # Lanzar task de Celery
        task = process_document_upload.delay(
            file_path=request.file_path,
            filename=request.filename,
            file_type=request.file_type,
            metadata=request.metadata or {}
        )
        
        ai_logger.logger.info(f"Document upload task queued: {task.id} for {request.filename}")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Document processing started for {request.filename}"
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to queue document upload task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start document processing: {str(e)}")

@router.post("/upload-batch", response_model=Dict[str, Any])
async def upload_batch_documents(request: BatchDocumentRequest):
    """
    Iniciar procesamiento asíncrono de múltiples documentos
    """
    try:
        # Preparar datos para batch
        documents_data = [
            {
                "file_path": doc.file_path,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "metadata": doc.metadata or {}
            }
            for doc in request.documents
        ]
        
        # Lanzar task batch
        task = process_document_upload.delay()  # Esto sería un task diferente
        
        ai_logger.logger.info(f"Batch document upload queued: {len(documents_data)} documents")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "total_documents": len(documents_data),
            "message": f"Batch processing started for {len(documents_data)} documents"
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to queue batch upload task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start batch processing: {str(e)}")

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_endpoint(task_id: str):
    """
    Obtener estado de una tarea específica
    """
    try:
        # Obtener resultado del task
        result = celery_app.AsyncResult(task_id)
        
        # Determinar progreso
        progress = 0
        info = None
        
        if result.state == 'PROCESSING' and result.info:
            info = result.info
            progress = info.get('progress', 0)
        elif result.state == 'FAILURE':
            info = result.info
        
        return TaskStatusResponse(
            task_id=task_id,
            state=result.state,
            result=result.result if result.ready() else None,
            info=info,
            progress=progress
        )
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to get task status {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@router.post("/embeddings/batch", response_model=Dict[str, str])
async def generate_embeddings_batch_async(request: EmbeddingBatchRequest):
    """
    Generar embeddings en batch de forma asíncrona
    """
    try:
        if not request.texts:
            raise HTTPException(status_code=400, detail="No texts provided")
        
        # Lanzar task de embeddings
        task = generate_embeddings_batch.delay(
            texts=request.texts,
            metadata=request.metadata or {}
        )
        
        ai_logger.logger.info(f"Embedding batch task queued: {task.id} for {len(request.texts)} texts")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Embedding generation started for {len(request.texts)} texts"
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to queue embedding batch task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start embedding generation: {str(e)}")

@router.post("/reindex/{document_id}", response_model=Dict[str, str])
async def reindex_document_async(document_id: str):
    """
    Re-indexar embeddings de un documento específico
    """
    try:
        # Lanzar task de reindexación
        task = reindex_document_embeddings.delay(document_id)
        
        ai_logger.logger.info(f"Document reindex task queued: {task.id} for document {document_id}")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Document reindexing started for {document_id}"
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to queue reindex task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start document reindexing: {str(e)}")

@router.delete("/document/{document_id}", response_model=Dict[str, str])
async def delete_document_async(document_id: str):
    """
    Eliminar documento de forma asíncrona
    """
    try:
        # Lanzar task de eliminación
        task = delete_document_task.delay(document_id)
        
        ai_logger.logger.info(f"Document deletion task queued: {task.id} for document {document_id}")
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Document deletion started for {document_id}"
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to queue delete task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start document deletion: {str(e)}")

@router.get("/workers", response_model=Dict[str, Any])
async def get_workers_status():
    """
    Obtener estado de los workers Celery
    """
    try:
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
        
        return {
            "workers": {
                "count": len(stats) if stats else 0,
                "details": stats or {}
            },
            "active_tasks": {
                "count": len(active_tasks),
                "details": active_tasks
            },
            "timestamp": ai_logger.logger.handlers[0].formatter.formatTime(ai_logger.logger.makeRecord(
                "", 0, "", 0, "", (), None
            )) if ai_logger.logger.handlers else None
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to get workers status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workers status: {str(e)}")

@router.get("/queue/stats", response_model=Dict[str, Any])
async def get_queue_stats():
    """
    Obtener estadísticas de las colas Celery
    """
    try:
        inspect = celery_app.control.inspect()
        
        # Obtener stats de colas
        stats = inspect.stats()
        
        # Contar tasks por cola
        queue_stats = {}
        if stats:
            for worker_name, worker_stats in stats.items():
                queues = worker_stats.get('pool', {}).get('max-concurrency', 0)
                queue_stats[worker_name] = {
                    'max_concurrency': queues,
                    'status': 'active'
                }
        
        return {
            "queues": queue_stats,
            "total_workers": len(stats) if stats else 0,
            "timestamp": ai_logger.logger.handlers[0].formatter.formatTime(ai_logger.logger.makeRecord(
                "", 0, "", 0, "", (), None
            )) if ai_logger.logger.handlers else None
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue stats: {str(e)}")

@router.post("/cancel/{task_id}", response_model=Dict[str, str])
async def cancel_task(task_id: str):
    """
    Cancelar una tarea específica
    """
    try:
        # Revocar task
        celery_app.control.revoke(task_id, terminate=True)
        
        ai_logger.logger.info(f"Task cancelled: {task_id}")
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": f"Task {task_id} has been cancelled"
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to cancel task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")

@router.get("/active", response_model=List[Dict[str, Any]])
async def get_active_tasks():
    """
    Obtener lista de tareas activas
    """
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        
        tasks_list = []
        if active_tasks:
            for worker_name, tasks in active_tasks.items():
                for task in tasks:
                    tasks_list.append({
                        'task_id': task['id'],
                        'name': task['name'],
                        'worker': worker_name,
                        'time_start': task.get('time_start'),
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {})
                    })
        
        return tasks_list
        
    except Exception as e:
        ai_logger.logger.error(f"Failed to get active tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active tasks: {str(e)}")
