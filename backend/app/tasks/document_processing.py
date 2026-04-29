# app/tasks/document_processing.py
import os
import tempfile
from typing import Dict, Any, Optional
from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.celery_app import celery_app
from app.core.database import get_db
from app.core.ai_logger import ai_logger
from app.core.metrics import ai_metrics
from app.core.cache import cache_manager
from app.services.rag_service import rag_service
from app.services.document_processor import DocumentProcessor

@celery_app.task(bind=True, name="app.tasks.document_processing.process_document_upload")
def process_document_upload(self, file_path: str, filename: str, file_type: str, metadata: Dict[str, Any] = None):
    """
    Task asíncrono para procesar upload de documentos
    - Extrae texto del archivo
    - Indexa en la base de datos
    - Genera embeddings
    """
    try:
        # Actualizar estado del task
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Starting document processing', 'progress': 0}
        )
        
        ai_logger.logger.info(f"Starting async document processing: {filename}")
        
        # Leer contenido del archivo
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Procesar documento
        processor = DocumentProcessor()
        
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Extracting text content', 'progress': 25}
        )
        
        # Extraer texto
        content = processor.extract_text(file_content, file_type, filename)
        
        if not content:
            raise ValueError(f"No se pudo extraer contenido del archivo: {filename}")
        
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Indexing document', 'progress': 50}
        )
        
        # Indexar documento en base de datos
        async def index_document():
            async for db in get_db():
                document_id = await rag_service.index_document(
                    db=db,
                    filename=filename,
                    content=content,
                    file_type=file_type,
                    metadata=metadata or {}
                )
                return document_id
        
        import asyncio
        document_id = asyncio.run(index_document())
        
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Cleaning up temporary files', 'progress': 75}
        )
        
        # Limpiar archivo temporal
        try:
            os.unlink(file_path)
        except OSError:
            pass
        
        # Limpiar caché relacionado
        asyncio.run(cache_manager.clear_pattern("embedding:*"))
        asyncio.run(cache_manager.clear_pattern("rag:*"))
        
        # Registrar métricas
        ai_metrics.increment_counter("documents_processed_total")
        ai_metrics.record_document_processing(
            file_type=file_type,
            file_size=len(file_content),
            chunk_count=0,  # Se obtendría de la BD
            duration=0,     # Se calcularía si tenemos tiempo
            success=True
        )
        
        self.update_state(
            state='SUCCESS',
            meta={
                'status': 'Document processed successfully',
                'progress': 100,
                'document_id': str(document_id),
                'filename': filename
            }
        )
        
        ai_logger.logger.info(f"Document processed successfully: {filename} (ID: {document_id})")
        
        return {
            'status': 'success',
            'document_id': str(document_id),
            'filename': filename,
            'file_type': file_type,
            'content_length': len(content)
        }
        
    except Exception as e:
        # Limpiar archivo temporal en caso de error
        try:
            os.unlink(file_path)
        except OSError:
            pass
        
        # Registrar error
        ai_logger.logger.error(f"Document processing failed: {filename} - {str(e)}")
        ai_metrics.increment_counter("documents_processing_failed")
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': f'Processing failed: {str(e)}',
                'filename': filename,
                'error': str(e)
            }
        )
        
        raise

@celery_app.task(bind=True, name="app.tasks.document_processing.batch_process_documents")
def batch_process_documents(self, documents: list):
    """
    Task para procesar múltiples documentos en batch
    """
    results = []
    total_docs = len(documents)
    
    ai_logger.logger.info(f"Starting batch processing of {total_docs} documents")
    
    for i, doc_data in enumerate(documents):
        try:
            # Lanzar task individual
            result = process_document_upload.delay(**doc_data)
            
            # Actualizar progreso del batch
            progress = int((i + 1) / total_docs * 100)
            self.update_state(
                state='PROCESSING',
                meta={
                    'status': f'Processed {i + 1}/{total_docs} documents',
                    'progress': progress,
                    'current_task': result.id
                }
            )
            
            results.append({
                'task_id': result.id,
                'filename': doc_data.get('filename'),
                'status': 'queued'
            })
            
        except Exception as e:
            ai_logger.logger.error(f"Failed to queue document {doc_data.get('filename')}: {e}")
            results.append({
                'filename': doc_data.get('filename'),
                'status': 'failed',
                'error': str(e)
            })
    
    return {
        'status': 'batch_queued',
        'total_documents': total_docs,
        'results': results
    }

@celery_app.task(bind=True, name="app.tasks.document_processing.delete_document")
def delete_document_task(self, document_id: str):
    """
    Task asíncrono para eliminar documento y sus chunks
    """
    try:
        async def delete_doc():
            async for db in get_db():
                from sqlalchemy import select, delete
                from app.models.document import Document, DocumentChunk
                
                # Eliminar chunks primero
                await db.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
                )
                
                # Eliminar documento
                result = await db.execute(
                    delete(Document).where(Document.id == document_id)
                )
                
                await db.commit()
                return result.rowcount
        
        import asyncio
        deleted_count = asyncio.run(delete_doc())
        
        if deleted_count > 0:
            # Limpiar caché relacionado
            asyncio.run(cache_manager.clear_pattern("rag:*"))
            asyncio.run(cache_manager.clear_pattern("embedding:*"))
            
            ai_metrics.increment_counter("documents_deleted_total")
            ai_logger.logger.info(f"Document deleted successfully: {document_id}")
            
            return {
                'status': 'success',
                'document_id': document_id,
                'deleted_count': deleted_count
            }
        else:
            raise ValueError(f"Document not found: {document_id}")
            
    except Exception as e:
        ai_logger.logger.error(f"Failed to delete document {document_id}: {e}")
        ai_metrics.increment_counter("documents_deletion_failed")
        raise

@celery_app.task(name="app.tasks.document_processing.get_task_status")
def get_task_status(task_id: str):
    """
    Task para obtener estado de otro task
    """
    try:
        result = celery_app.AsyncResult(task_id)
        
        return {
            'task_id': task_id,
            'state': result.state,
            'result': result.result if result.ready() else None,
            'info': result.info if result.state == 'FAILURE' else None,
            'progress': result.info.get('progress', 0) if result.info else 0
        }
    except Exception as e:
        ai_logger.logger.error(f"Failed to get task status {task_id}: {e}")
        raise
