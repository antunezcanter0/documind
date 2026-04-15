from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
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

    # Vector embeddings se manejarán con pgvector en otra tabla


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