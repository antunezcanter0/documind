# app/api/documents.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.services.rag_service import rag_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db)
):
    """Subir un documento para indexar en el sistema RAG"""

    # Validar tipo de archivo
    allowed_types = ["text/plain", "application/pdf", "text/markdown"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"Tipo no soportado. Permitidos: {allowed_types}")

    try:
        # Leer contenido
        content = await file.read()
        text_content = content.decode("utf-8")

        # Usar rag_service para indexar el documento
        doc_id = await rag_service.index_document(
            db=db,
            filename=file.filename,
            content=text_content,
            file_type=file.content_type,
            metadata={"original_name": file.filename}
        )

        return {
            "message": "Documento indexado exitosamente",
            "document_id": str(doc_id),
            "filename": file.filename,
            "size": len(content),
            "status": "success"
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error procesando documento: {str(e)}")


@router.get("/list")
async def list_documents(
        skip: int = 0,
        limit: int = 100,
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