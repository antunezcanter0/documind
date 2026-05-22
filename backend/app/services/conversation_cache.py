# app/services/conversation_cache.py
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.document import Conversation

class ConversationCache:
    """Gestiona el contexto conversacional usando base de datos"""
    
    def __init__(self):
        self.max_messages = 10  # Máximo de mensajes por conversación
    
    async def add_message(
        self,
        db: Session,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        """Añadir un mensaje a la conversación"""
        # Buscar conversación existente
        conversation = db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        ).scalar_one_or_none()
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        if conversation:
            # Añadir mensaje a la conversación existente
            messages = conversation.messages or []
            messages.append(message)
            
            # Mantener solo los últimos N mensajes
            if len(messages) > self.max_messages:
                messages = messages[-self.max_messages:]
            
            conversation.messages = messages
            conversation.updated_at = datetime.utcnow()
        else:
            # Crear nueva conversación
            conversation = Conversation(
                session_id=session_id,
                messages=[message],
                conv_metadata={}
            )
            db.add(conversation)
        
        db.commit()
    
    async def get_context(
        self,
        db: Session,
        session_id: str,
        last_n: int = 5
    ) -> List[Dict]:
        """Obtener los últimos N mensajes de la conversación"""
        conversation = db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        ).scalar_one_or_none()
        
        if not conversation or not conversation.messages:
            return []
        
        messages = conversation.messages
        return messages[-last_n:] if len(messages) > last_n else messages
    
    async def get_full_conversation(self, db: Session, session_id: str) -> List[Dict]:
        """Obtener toda la conversación"""
        conversation = db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        ).scalar_one_or_none()
        
        return conversation.messages if conversation else []
    
    async def clear_conversation(self, db: Session, session_id: str):
        """Limpiar una conversación específica"""
        conversation = db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        ).scalar_one_or_none()
        
        if conversation:
            db.delete(conversation)
            db.commit()
    
    async def get_conversation_stats(self, db: Session, session_id: str) -> Dict:
        """Obtener estadísticas de una conversación"""
        conversation = db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        ).scalar_one_or_none()
        
        if not conversation:
            return {
                "message_count": 0,
                "exists": False,
                "created_at": None,
                "updated_at": None
            }
        
        return {
            "message_count": len(conversation.messages) if conversation.messages else 0,
            "exists": True,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None
        }

# Instancia global
conversation_cache = ConversationCache()
