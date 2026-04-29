# app/services/rag_service.py
import hashlib
import time
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service
from app.core.ai_logger import ai_logger, log_performance
from app.core.cache import cache_manager, cache_rag_response


class RAGService:
    """Servicio principal para indexación y búsqueda de documentos"""

    @staticmethod
    async def index_document(
            db: AsyncSession,
            filename: str,
            content: str,
            file_type: str,
            metadata: Dict[str, Any] = None
    ) -> UUID:
        """
        Procesa un documento completo:
        1. Calcula hash para evitar duplicados
        2. Divide en chunks
        3. Genera embeddings para cada chunk
        4. Guarda en base de datos
        """
        # 1. Calcular hash del contenido
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # 2. Verificar si ya existe (evitar duplicados)
        existing = await db.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"El documento '{filename}' ya fue indexado anteriormente")

        # 3. Dividir en chunks
        chunks = embedding_service.chunk_text(content)

        # 4. Generar embeddings para todos los chunks
        chunk_texts = [chunk for chunk in chunks]
        embeddings = await embedding_service.get_embeddings(chunk_texts)

        # 5. Crear el documento en BD
        document = Document(
            filename=filename,
            content=content,
            content_hash=content_hash,
            file_type=file_type,
            chunk_count=len(chunks),
            doc_metadata=metadata or {}
        )
        db.add(document)
        await db.flush()  # Para obtener el ID del documento

        # 6. Crear los chunks con sus embeddings
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                content=chunk_text,
                embedding=embedding
            )
            db.add(chunk)

        await db.commit()
        await db.refresh(document)

        print(f"✅ Documento indexado: {filename} ({len(chunks)} chunks)")
        return document.id

    @staticmethod
    async def search(
            db: AsyncSession,
            query: str,
            top_k: int = 5,
            similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Busca los chunks más similares a la consulta usando similitud coseno
        """
        # 1. Generar embedding de la consulta
        query_embedding = await embedding_service.get_embedding(query)

        # 2. Búsqueda por similitud coseno (<=> es distancia coseno)
        # Menor distancia = mayor similitud
        stmt = (
            select(
                DocumentChunk,
                Document.filename,
                Document.doc_metadata,
                (1 - func.abs(DocumentChunk.embedding.cosine_distance(query_embedding))).label("similarity")
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )

        result = await db.execute(stmt)
        rows = result.all()

        # 3. Formatear resultados
        results = []
        for row in rows:
            chunk, filename, doc_metadata, similarity = row
            if similarity >= similarity_threshold:
                results.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "filename": filename,
                    "content": chunk.content,
                    "similarity": float(similarity),
                    "chunk_index": chunk.chunk_index,
                    "metadata": doc_metadata
                })

        return results

    @staticmethod
    @cache_rag_response()
    @log_performance
    async def answer_question(
            db: AsyncSession,
            question: str,
            top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Responde una pregunta usando RAG:
        1. Busca chunks relevantes
        2. Construye un prompt con el contexto
        3. Llama al LLM para generar la respuesta
        """
        start_time = time.time()
        
        # 1. Buscar chunks relevantes
        relevant_chunks = await RAGService.search(db, question, top_k)

        if not relevant_chunks:
            duration = time.time() - start_time
            ai_logger.log_rag_operation(
                query=question,
                documents_found=0,
                chunks_used=0,
                duration=duration,
                has_context=False
            )
            return {
                "answer": "No encontré información relevante en los documentos para responder tu pregunta.",
                "sources": [],
                "has_context": False
            }

        # 2. Construir el contexto
        context = "\n\n---\n\n".join([
            f"[Documento: {chunk['filename']} - Fragmento {chunk['chunk_index']}]\n{chunk['content']}"
            for chunk in relevant_chunks
        ])

        # 3. Construir el prompt
        prompt = f"""Eres un asistente especializado en responder preguntas basándote ÚNICAMENTE en el contexto proporcionado.

CONTEXTO:
{context}

PREGUNTA: {question}

INSTRUCCIONES:
- Responde SOLO usando la información del contexto
- Si la respuesta no está en el contexto, di "No encontré información sobre esto en los documentos"
- Cita las fuentes usando [Nombre del documento]
- Sé conciso y preciso

RESPUESTA:"""

        # 4. Llamar al LLM
        messages = [{"role": "user", "content": prompt}]
        answer = await llm_service.chat_completion(messages, temperature=0.3)

        # 5. Preparar las fuentes para la respuesta
        sources = list({
                           chunk["filename"]: {
                               "filename": chunk["filename"],
                               "similarity": chunk["similarity"]
                           }
                           for chunk in relevant_chunks
                       }.values())

        # 6. Loggear operación RAG
        duration = time.time() - start_time
        ai_logger.log_rag_operation(
            query=question,
            documents_found=len(set(chunk["filename"] for chunk in relevant_chunks)),
            chunks_used=len(relevant_chunks),
            duration=duration,
            has_context=True,
            metadata={"avg_similarity": sum(chunk["similarity"] for chunk in relevant_chunks) / len(relevant_chunks)}
        )

        return {
            "answer": answer,
            "sources": sources,
            "has_context": True,
            "chunks_used": len(relevant_chunks)
        }


rag_service = RAGService()