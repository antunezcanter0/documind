# app/api/documents.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.auth import get_current_active_user, require_permission
from app.models.user import User
from app.services.rag_service import rag_service

from app.services.document_processor import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
        file: UploadFile = File(...),
        current_user: User = Depends(require_permission("documents", "write")),
        db: AsyncSession = Depends(get_db)
):
    """Subir un documento para indexar en el sistema RAG"""

    # Validar tipo de archivo
    allowed_types = [
        "text/plain",
        "text/markdown",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/html",
        "application/msword",  # .doc antiguo
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            400,
            f"Tipo no soportado. Permitidos: {allowed_types}"
        )

    try:
        # Leer contenido
        content = await file.read()

        # Validar tamaño máximo (10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise HTTPException(400, f"Archivo demasiado grande. Máximo: 10MB")

        # text_content = content.decode("utf-8")
        # Procesar según el tipo de archivo
        text_content, metadata = await DocumentProcessor.process_document(
            content=content,
            content_type=file.content_type
        )

        # Verificar que se extrajo texto
        if not text_content or len(text_content.strip()) < 10:
            raise HTTPException(400, "No se pudo extraer texto del documento o es demasiado corto")

        # Usar rag_service para indexar el documento
        doc_id = await rag_service.index_document(
            db=db,
            filename=file.filename,
            content=text_content,
            file_type=file.content_type,
            metadata={
                "original_name": file.filename,
                "processed_metadata": metadata,
                "size_bytes": len(content)
            }
        )

        return {
            "message": "Documento indexado exitosamente",
            "document_id": str(doc_id),
            "filename": file.filename,
            "size": len(content),
            "text_length": len(text_content),
            "file_type": file.content_type,
            "metadata": metadata,
            "status": "success"
        }


    except ValueError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(500, f"Error procesando documento: {str(e)}")


@router.get("/list")
async def list_documents(
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(require_permission("documents", "read")),
        db: AsyncSession = Depends(get_db)
):
    """Listar documentos procesados"""
    from sqlalchemy import select
    from app.models.document import Document

    result = await db.execute(
        select(Document).offset(skip).limit(limit)
    )
    documents = result.scalars().all()

    return {
        "documents": [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "file_type": doc.file_type,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in documents
        ],
        "total": len(documents)
    }