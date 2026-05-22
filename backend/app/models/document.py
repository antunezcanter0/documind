from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from pgvector.sqlalchemy import Vector
import uuid


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), unique=True)  # Para evitar duplicados
    file_type = Column(String(50))  # pdf, txt, md, etc.
    chunk_count = Column(Integer, default=0)
    doc_metadata = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768))  # 768 para nomic-embed-text

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Índice para búsqueda rápida por similitud (IVFFlat o HNSW)
    # Usaremos HNSW que es más moderno y preciso
    __table_args__ = (
        Index('idx_chunk_embedding', embedding, postgresql_using='hnsw', 
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    messages = Column(JSON, default=list)  # [{"role": "user", "content": "...", "timestamp": "..."}]
    conv_metadata = Column(JSON, default=dict)  # Renombrado para evitar conflicto con metadata reservado
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_conversation_session', 'session_id'),
    )