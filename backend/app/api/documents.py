# app/api/documents.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.core.database import get_db
from app.services.rag_service import RAGService  # ← Cambiar importación
from app.services.document_processor import DocumentProcessor
from app.models.document import Document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """Subir un documento para indexar en el sistema RAG"""

    # Validar tipo de archivo
    allowed_types = [
        "application/octet-stream", # Para archivos .fop y otros binarios
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"Tipo no soportado: {file.filename}")

    try:
        # Leer contenido
        content = await file.read()

        # Decodificar contenido para FOP files
        text_content = None
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                text_content = content.decode(enc)
                break
            except:
                continue

        if not text_content:
            raise ValueError("No se pudo decodificar el archivo")

        # Extraer metadata básica
        metadata = {
            "original_name": file.filename,
            "type": "fop" if file.filename.lower().endswith('.fop') else "unknown"
        }
        

        try:
            doc_id = await RAGService.index_document(
                db=db,
                filename=file.filename,
                content=text_content,
                file_type=file.content_type,
                metadata=metadata
            )
        except Exception as e:
            return {
                "message": str(e),
                "filename": file.filename,
                "size": len(content),
                "text_length": len(text_content),
                "status": "error",
            }

        return {
            "message": "Documento indexado exitosamente",
            "document_id": str(doc_id),
            "filename": file.filename,
            "size": len(content),
            "text_length": len(text_content),
            "status": "success"
        }

    except ValueError as e:
        print(f"Error: {str(e)}")
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"Error procesando documento: {str(e)}")
        raise HTTPException(500, f"Error procesando documento: {str(e)}")


@router.get("/list")
async def list_documents(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """Listar documentos procesados"""
    result = db.execute(
        select(Document).offset(skip).limit(limit)
    )
    documents = result.scalars().all()

    return {
        "documents": [
            {
                "document_id": str(doc.id),
                "filename": doc.filename,
                "file_type": doc.file_type,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in documents
        ],
        "total": len(documents)
    }