from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import uuid
import hashlib
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import EmbeddingService


class DocumentService:
    
    @staticmethod
    async def process_document(
        db: AsyncSession, 
        filename: str, 
        content: str,
        file_type: str = "text"
    ) -> dict:
        """Procesar un documento: extraer texto, generar embeddings y guardar en BD"""
        
        # Generar hash para evitar duplicados
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Verificar si ya existe
        existing = await db.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        if existing.scalar_one_or_none():
            return {"status": "duplicate", "document_id": str(existing.scalar_one().id)}
        
        # Crear documento
        document = Document(
            id=uuid.uuid4(),
            filename=filename,
            content=content,
            content_hash=content_hash,
            file_type=file_type
        )
        
        db.add(document)
        await db.flush()  # Para obtener el ID
        
        # Dividir en chunks (simplificado)
        chunks = DocumentService._split_text(content)
        
        # Generar embeddings y guardar chunks
        embedding_service = EmbeddingService()
        for i, chunk_text in enumerate(chunks):
            embedding = await embedding_service.get_embedding(chunk_text)
            
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=i,
                content=chunk_text,
                embedding=embedding
            )
            db.add(chunk)
        
        # Actualizar conteo de chunks
        document.chunk_count = len(chunks)
        
        await db.commit()
        
        return {
            "status": "processed",
            "document_id": str(document.id),
            "chunks_count": len(chunks)
        }
    
    @staticmethod
    def _split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Dividir texto en chunks con solapamiento"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Si no es el último chunk, intentar cortar en espacio o punto
            if end < len(text):
                last_space = chunk.rfind(' ')
                last_period = chunk.rfind('.')
                
                cut_pos = max(last_space, last_period)
                if cut_pos > chunk_size * 0.8:  # No hacer chunks muy pequeños
                    chunk = chunk[:cut_pos + 1]
                    end = start + cut_pos + 1
            
            chunks.append(chunk.strip())
            
            if end >= len(text):
                break
                
            start = end - overlap
            
        return [c for c in chunks if c.strip()]
    
    @staticmethod
    async def get_documents(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Document]:
        """Obtener lista de documentos"""
        result = await db.execute(
            select(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_document_by_id(
        db: AsyncSession, 
        document_id: str
    ) -> Optional[Document]:
        """Obtener documento por ID"""
        result = await db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def delete_document(
        db: AsyncSession, 
        document_id: str
    ) -> bool:
        """Eliminar documento y sus chunks"""
        # Primero eliminar chunks
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
        )
        
        # Luego eliminar documento
        result = await db.execute(
            delete(Document).where(Document.id == uuid.UUID(document_id))
        )
        
        await db.commit()
        return result.rowcount > 0
