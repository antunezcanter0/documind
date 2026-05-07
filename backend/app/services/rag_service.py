import hashlib
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service


class RAGService:

    # =========================
    # INDEXACIÓN OPTIMIZADA
    # =========================
    @staticmethod
    async def index_document(
        db: Session,
        filename: str,
        content: str,
        file_type: str,
        metadata: Dict[str, Any] = None
    ) -> UUID:

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # 🔥 duplicados por contenido
        existing = db.execute(
            select(Document).where(Document.content_hash == content_hash)
        ).scalar_one_or_none()

        if existing:
            print(f"⚠️ Documento duplicado: {filename}")
            return existing.id

        # 🔥 update por nombre
        existing_by_name = db.execute(
            select(Document).where(Document.filename == filename)
        ).scalar_one_or_none()

        if existing_by_name:
            print(f"🔄 Reindexando: {filename}")

            chunks_to_delete = db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == existing_by_name.id
                )
            ).scalars().all()

            for c in chunks_to_delete:
                db.delete(c)

            db.delete(existing_by_name)
            db.commit()

        # =========================
        # CHUNKING FOP (YA VIENE PROCESADO)
        # =========================
        if file_type == "text/x-fop":
            chunks = content.split("\n\n")
        else:
            chunks = embedding_service.chunk_text(content)

        print(f"📄 chunks generados: {len(chunks)}")

        # =========================
        # EMBEDDINGS (BATCH)
        # =========================
        embeddings = await embedding_service.get_embeddings(chunks)

        # =========================
        # DOCUMENTO
        # =========================
        document = Document(
            filename=filename,
            content=content,
            content_hash=content_hash,
            file_type=file_type,
            chunk_count=len(chunks),
            doc_metadata=metadata or {}
        )

        db.add(document)
        db.flush()

        # =========================
        # BULK INSERT CHUNKS
        # =========================
        db_chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk,
                embedding=emb
            )
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]

        db.bulk_save_objects(db_chunks)
        db.commit()

        print(f"✅ Indexado: {filename}")
        return document.id

    # =========================
    # SEARCH OPTIMIZADO
    # =========================
    @staticmethod
    async def search(db: Session, query: str, top_k: int = 5):

        expanded_query = f"""
        {query}
        
        Relacionado con comandos de telecomunicaciones y líneas de abonado.
        """

        query_embedding = await embedding_service.get_embedding(expanded_query)

        stmt = (
            select(
                DocumentChunk,
                Document.filename,
                Document.doc_metadata,
                (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .select_from(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(30)
        )

        rows = db.execute(stmt).all()

        results = []

        for chunk, filename, metadata, similarity in rows:

            bonus = 0.0
            q = query.lower()
            c = chunk.content.lower()

            if "crear" in q and "crear" in c:
                bonus += 0.1
            if "abonado" in q and "abonado" in c:
                bonus += 0.1
            if metadata and metadata.get("command") and metadata["command"] in c:
                bonus += 0.1

            score = min(1.0, similarity + bonus)

            if score > 0.5:
                results.append({
                    "content": chunk.content,
                    "filename": filename,
                    "similarity": score,
                    "metadata": metadata
                })

        return sorted(results, key=lambda x: x["similarity"], reverse=True)[:top_k]

    # =========================
    # ANSWER (SIN CAMBIOS MAYORES)
    # =========================
    @staticmethod
    async def answer_question(db: Session, question: str, top_k: int = 5):

        chunks = await RAGService.search(db, question, top_k)

        if not chunks:
            return {
                "answer": "No encontré información relevante.",
                "has_context": False
            }

        context = "\n\n---\n\n".join([
            f"[{c['filename']}]\n{c['content']}"
            for c in chunks
        ])

        prompt = f"""
        Eres un experto en telecomunicaciones.
        
        Responde SOLO con el contexto.
        
        CONTEXTO:
        {context}
        
        PREGUNTA:
        {question}
        """

        answer = await llm_service.chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.3
        )

        sources = list({
            c["filename"]: {
                "filename": c["filename"],
                "similarity": c["similarity"]
            }
            for c in chunks
        }.values())

        return {
            "answer": answer,
            "sources": sources,
            "has_context": True,
            "chunks_used": len(chunks)
        }