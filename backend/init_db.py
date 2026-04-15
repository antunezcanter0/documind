# init_db.py
import asyncio
from app.core.database import engine, Base
from app.models.document import Document, DocumentChunk
from sqlalchemy import text


async def init_db():
    """Crear todas las tablas y extensiones necesarias"""
    async with engine.begin() as conn:
        # Habilitar extensión vector (si no existe)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Crear todas las tablas definidas en los modelos
        await conn.run_sync(Base.metadata.create_all)

        print("✅ Base de datos inicializada correctamente")
        print("   - Extensión 'vector' habilitada")
        print("   - Tabla 'documents' creada")
        print("   - Tabla 'document_chunks' creada con índice HNSW")


if __name__ == "__main__":
    asyncio.run(init_db())