# app/api/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.core.database import get_db
from app.services.rag_service import RAGService
from app.services.llm_service import llm_service
from app.services.conversation_cache import conversation_cache

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    use_rag: bool = True
    top_k: int = 5
    session_id: Optional[str] = None  # Para contexto conversacional


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
        db: Session = Depends(get_db)
):
    """Hacer una pregunta usando RAG sobre los documentos indexados con contexto conversacional"""

    # Obtener contexto conversacional si hay session_id
    conversation_context = []
    if request.session_id:
        conversation_context = await conversation_cache.get_context(
            db,
            request.session_id,
            last_n=5  # Últimos 5 mensajes
        )

    if request.use_rag:
        # Usar RAG para responder con contexto
        result = await RAGService.answer_question(
            db=db,
            question=request.question,
            top_k=request.top_k,
            conversation_context=conversation_context
        )
        
        # Guardar en historial si hay session_id
        if request.session_id:
            await conversation_cache.add_message(
                db,
                session_id=request.session_id,
                role="user",
                content=request.question
            )
            await conversation_cache.add_message(
                db,
                session_id=request.session_id,
                role="assistant",
                content=result["answer"],
                metadata={"sources": result.get("sources", [])}
            )
        
        return ChatResponse(**result)
    else:
        # Respuesta directa del LLM (sin contexto de documentos)
        messages = []
        
        # Añadir contexto conversacional si existe
        if conversation_context:
            messages.extend(conversation_context)
        
        # Añadir pregunta actual
        messages.append({"role": "user", "content": request.question})
        
        answer = await llm_service.chat_completion(messages)
        
        # Guardar en historial si hay session_id
        if request.session_id:
            await conversation_cache.add_message(
                db,
                session_id=request.session_id,
                role="user",
                content=request.question
            )
            await conversation_cache.add_message(
                db,
                session_id=request.session_id,
                role="assistant",
                content=answer
            )
        
        return ChatResponse(
            answer=answer,
            sources=[],
            has_context=False,
            chunks_used=None
        )


@router.post("/search")
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Buscar documentos relevantes sin generar respuesta"""
    results = await RAGService.search(db, request.query, request.top_k)
    return {"results": results, "count": len(results)}


@router.delete("/conversation/{session_id}")
async def clear_conversation(session_id: str, db: Session = Depends(get_db)):
    """Limpiar el historial de una conversación específica"""
    await conversation_cache.clear_conversation(db, session_id)
    return {"message": "Conversación limpiada", "session_id": session_id}


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str, db: Session = Depends(get_db)):
    """Obtener el historial completo de una conversación"""
    conversation = await conversation_cache.get_full_conversation(db, session_id)
    stats = await conversation_cache.get_conversation_stats(db, session_id)
    return {
        "conversation": conversation,
        "stats": stats
    }
