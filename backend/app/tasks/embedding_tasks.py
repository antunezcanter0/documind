# app/tasks/embedding_tasks.py
from typing import List, Dict, Any
from celery import current_task
from app.core.celery_app import celery_app
from app.core.ai_logger import ai_logger
from app.core.metrics import ai_metrics
from app.core.cache import cache_manager
from app.services.embedding_service import embedding_service

@celery_app.task(bind=True, name="app.tasks.embedding_tasks.generate_embeddings_batch")
def generate_embeddings_batch(self, texts: List[str], metadata: Dict[str, Any] = None):
    """
    Task para generar embeddings en batch para múltiples textos
    """
    try:
        total_texts = len(texts)
        ai_logger.logger.info(f"Starting batch embedding generation for {total_texts} texts")
        
        # Actualizar estado inicial
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Starting embedding generation', 'progress': 0}
        )
        
        # Generar embeddings
        embeddings = embedding_service.get_embeddings(texts)
        
        # Actualizar progreso
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Embeddings generated successfully', 'progress': 100}
        )
        
        # Registrar métricas
        ai_metrics.increment_counter("embedding_batches_total")
        total_chars = sum(len(text) for text in texts)
        ai_metrics.record_embedding_operation(
            model_name=embedding_service.model,
            text_length=total_chars,
            chunk_count=total_texts,
            duration=0,  # Se podría calcular si tenemos tiempo
            success=True
        )
        
        ai_logger.logger.info(f"Batch embedding generation completed: {total_texts} texts")
        
        return {
            'status': 'success',
            'embeddings': embeddings,
            'count': len(embeddings),
            'model': embedding_service.model,
            'total_chars': total_chars
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Batch embedding generation failed: {str(e)}")
        ai_metrics.increment_counter("embedding_batches_failed")
        
        self.update_state(
            state='FAILURE',
            meta={'status': f'Embedding generation failed: {str(e)}', 'error': str(e)}
        )
        
        raise

@celery_app.task(bind=True, name="app.tasks.embedding_tasks.reindex_document_embeddings")
def reindex_document_embeddings(self, document_id: str):
    """
    Task para re-generar embeddings de un documento específico
    """
    try:
        ai_logger.logger.info(f"Starting reindexing for document: {document_id}")
        
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Loading document content', 'progress': 25}
        )
        
        # Cargar documento y chunks
        async def load_document():
            async for db in get_db():
                from sqlalchemy import select
                from app.models.document import Document, DocumentChunk
                
                # Obtener documento
                doc_result = await db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                if not document:
                    raise ValueError(f"Document not found: {document_id}")
                
                # Obtener chunks
                chunks_result = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
                chunks = chunks_result.scalars().all()
                
                return document, chunks
        
        import asyncio
        document, chunks = asyncio.run(load_document())
        
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Generating new embeddings', 'progress': 50}
        )
        
        # Generar nuevos embeddings
        chunk_texts = [chunk.content for chunk in chunks]
        new_embeddings = embedding_service.get_embeddings(chunk_texts)
        
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Updating embeddings in database', 'progress': 75}
        )
        
        # Actualizar embeddings en base de datos
        async def update_embeddings():
            async for db in get_db():
                for chunk, embedding in zip(chunks, new_embeddings):
                    chunk.embedding = embedding
                    db.add(chunk)
                
                await db.commit()
        
        asyncio.run(update_embeddings())
        
        # Limpiar caché relacionado
        asyncio.run(cache_manager.clear_pattern("embedding:*"))
        asyncio.run(cache_manager.clear_pattern("rag:*"))
        
        self.update_state(
            state='SUCCESS',
            meta={'status': 'Document reindexed successfully', 'progress': 100}
        )
        
        ai_logger.logger.info(f"Document reindexed successfully: {document_id}")
        
        return {
            'status': 'success',
            'document_id': document_id,
            'filename': document.filename,
            'chunks_updated': len(chunks),
            'model': embedding_service.model
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Document reindexing failed {document_id}: {str(e)}")
        ai_metrics.increment_counter("document_reindexing_failed")
        
        self.update_state(
            state='FAILURE',
            meta={'status': f'Reindexing failed: {str(e)}', 'error': str(e)}
        )
        
        raise

@celery_app.task(name="app.tasks.embedding_tasks.precompute_popular_embeddings")
def precompute_popular_embeddings():
    """
    Task periódico para pre-computar embeddings de textos comunes
    """
    try:
        ai_logger.logger.info("Starting precomputation of popular embeddings")
        
        # Textos comunes que podrían ser consultados frecuentemente
        common_texts = [
            "¿Qué es?",
            "¿Cómo funciona?",
            "¿Cuáles son los beneficios?",
            "¿Qué características tiene?",
            "¿Cómo puedo empezar?",
            "¿Dónde encuentro más información?",
            "¿Cuánto cuesta?",
            "¿Hay alguna limitación?",
            "¿Es seguro?",
            "¿Qué necesito para usarlo?"
        ]
        
        # Generar embeddings
        embeddings = embedding_service.get_embeddings(common_texts)
        
        # Almacenar en caché con TTL largo
        import asyncio
        for i, (text, embedding) in enumerate(zip(common_texts, embeddings)):
            cache_key = f"embedding:common:{i}"
            asyncio.run(cache_manager.set(cache_key, embedding, ttl=86400))  # 24 horas
        
        ai_metrics.increment_counter("precomputed_embeddings_total")
        ai_logger.logger.info(f"Precomputed {len(common_texts)} popular embeddings")
        
        return {
            'status': 'success',
            'precomputed_count': len(common_texts),
            'texts': common_texts
        }
        
    except Exception as e:
        ai_logger.logger.error(f"Precomputation failed: {str(e)}")
        ai_metrics.increment_counter("precomputation_failed")
        raise
