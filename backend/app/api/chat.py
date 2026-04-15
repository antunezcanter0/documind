# app/api/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.core.database import get_db
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    use_rag: bool = True
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict]
    has_context: bool
    chunks_used: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
        request: ChatRequest,
        db: AsyncSession = Depends(get_db)
):
    """Hacer una pregunta usando RAG sobre los documentos indexados"""

    if request.use_rag:
        # Usar RAG para responder
        result = await rag_service.answer_question(
            db=db,
            question=request.question,
            top_k=request.top_k
        )
        return ChatResponse(**result)
    else:
        # Respuesta directa del LLM (sin contexto)
        messages = [{"role": "user", "content": request.question}]
        answer = await llm_service.chat_completion(messages)
        return ChatResponse(
            answer=answer,
            sources=[],
            has_context=False,
            chunks_used=None
        )


@router.post("/search")
async def search_documents(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Buscar documentos relevantes sin generar respuesta"""
    results = await rag_service.search(db, request.query, request.top_k)
    return {"results": results, "count": len(results)}