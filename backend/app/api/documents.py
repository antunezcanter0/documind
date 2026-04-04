from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db)
):
    """Subir un documento para procesar"""
    # Validar tipo de archivo
    allowed_types = ["text/plain", "application/pdf", "text/markdown"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"Tipo no soportado. Permitidos: {allowed_types}")

    # Leer contenido
    content = await file.read()
    text_content = content.decode("utf-8")  # Simplificado, para PDF necesitarías PyPDF2

    # Servicio que crearemos después
    # result = await DocumentService.process_document(db, file.filename, text_content)

    return {
        "message": "Documento recibido",
        "filename": file.filename,
        "size": len(content),
        "status": "pending_processing"
    }


@router.get("/list")
async def list_documents(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """Listar documentos procesados"""
    # Implementar después
    return {"documents": [], "total": 0}