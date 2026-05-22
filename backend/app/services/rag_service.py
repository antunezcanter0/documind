import hashlib
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import func, case
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
        # CHUNKING ESPECIALIZADO POR TIPO DE ARCHIVO
        # =========================
        if filename.lower().endswith('.fop'):
            # Usar chunking especializado para archivos FOP
            print(f"📄 Generando chunks para {filename}")
            chunks = embedding_service.chunk_fop_text(content, filename)
        else:
            # Chunking tradicional para otros archivos
            chunks_raw = content.split("\n\n")
            chunks = []
            
            for i, chunk in enumerate(chunks_raw):
                # Limpiar chunk vacío
                chunk = chunk.strip()
                if not chunk:
                    continue
                # Para el primer chunk (semántico), añadir referencia al nombre del archivo
                if i == 0 and metadata:
                    chunk = f"{chunk}\n\n[DOCUMENTO: {filename}]"
                chunks.append(chunk)
            
            # Si los chunks son muy pocos, expandir usando chunk_text
            if len(chunks) < 3:
                expanded = []
                for chunk in chunks:
                    subchunks = embedding_service.chunk_text(chunk, chunk_size=800, overlap=100)
                    expanded.extend(subchunks)
                chunks = expanded
        
        print(f"📄 chunks generados: {len(chunks)}")
        
        # Debug: Mostrar primer chunk
        if chunks:
            print(f"🔍 Primer chunk (preview): {chunks[0][:200]}...")

        # =========================
        # EMBEDDINGS (BATCH)
        # =========================
        print("🔄 Generando embeddings...")
        embeddings = await embedding_service.get_embeddings(chunks)
        print(f"✅ Embeddings generados: {len(embeddings)}")

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
    # SEARCH OPTIMIZADO CON PALABRAS CLAVE
    # =========================
    @staticmethod
    async def search(db: Session, query: str, top_k: int = 5):
    
        # Mejorar procesamiento de query para comandos E10B genéricos
        query_upper = query.upper()
        expanded_terms = [query]
        
        # Detectar patrones de comandos E10B y expandir de forma genérica
        import re
        # Extraer posibles códigos de comando (ej: ABOCR, ACHCR, MILCR, etc.)
        command_patterns = re.findall(r'[A-Z]{3,6}[-]?\d{0,2}', query_upper)
        
        for pattern in command_patterns:
            expanded_terms.extend([
                pattern.replace('-', ''),     # ABOCR-01 -> ABOCR01
                pattern.replace('-', '') + '-01',  # ABOCR -> ABOCR-01
                'FA' + pattern.replace('-', ''),  # ABOCR -> FABOCR
                'FM' + pattern.replace('-', ''),  # ILCR -> FMILCR
            ])
        
        # Expandir sinónimos comunes de telecomunicaciones
        # telecom_synonyms = {
        #     'CREAR': ['alta', 'creación', 'nuevo', 'instalar', 'provisionar', 'agregar'],
        #     'BORRAR': ['eliminar', 'suprimir', 'baja', 'remover', 'quitar'],
        #     'MODIFICAR': ['cambiar', 'actualizar', 'editar', 'modificación', 'ajustar'],
        #     'CONSULTAR': ['ver', 'mostrar', 'listar', 'exhibir', 'consultar', 'visualizar'],
        #     'LISTAR': ['mostrar', 'visualizar', 'consultar', 'lis'],
        #     'ABONADO': ['cliente', 'usuario', 'línea', 'servicio', 'suscriptor'],
        #     'LINEA': ['conexión', 'circuito', 'terminal', 'enlace'],
        #     'ENCAMINAMIENTO': ['ruta', 'dirección', 'enrutamiento', 'camino'],
        #     'MILLARES': ['grupo', 'bloque', 'conjunto', 'milla'],
        #     'CARACTERISTICAS': ['caract', 'datos', 'información', 'parámetros']
        # }
        
        # for key, values in telecom_synonyms.items():
        #     if key in query_upper:
        #         expanded_terms.extend(values)
        #         expanded_terms.extend([query.replace(key.lower(), val) for val in values])
        
        expanded_query = f"""
        {query}
        
        {' '.join(expanded_terms)}
        
        Comandos de central telefónica E10B, telecomunicaciones, fichas operador.
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
            .limit(50)  # 🔥 Aumentado para permitir filtrado después
        )

        # 🔥 BÚSQUEDA INTELIGENTE POR PALABRAS CLAVE Y COMANDOS E10B
        query_lower = query.lower()
        query_upper = query.upper()
        
        # Extraer palabras clave (remover stopwords comunes)
        stopwords = {'que', 'se', 'usa', 'para', 'el', 'la', 'de', 'y', 'es', 'con', 'en', 'por', 'a', 'como', 'un', 'una'}
        keywords = [w for w in query_lower.split() if len(w) > 2 and w not in stopwords]
        
        # Extraer patrones de comandos E10B de forma genérica
        import re
        command_codes = re.findall(r'[A-Z]{3,6}[-]?\d{0,2}', query_upper)
        
        # Añadir variaciones de comandos
        for code in command_codes:
            keywords.extend([
                code.replace('-', ''),      # ABOCR-01 -> ABOCR01
                code.replace('-', '') + '-01',  # ABOCR -> ABOCR-01
                'FA' + code.replace('-', ''),  # ABOCR -> FABOCR
                'FM' + code.replace('-', ''),  # ILCR -> FMILCR
            ])
        
        # Construir condición OR para todos los términos de búsqueda
        keyword_filters = []
        for term in keywords:
            keyword_filters.append(DocumentChunk.content.ilike(f'%{term}%'))
        
        # Búsqueda especial para campos COMANDO: y CÓDIGO:
        for code in command_codes:
            keyword_filters.append(DocumentChunk.content.ilike(f'%CÓDIGO%{code}%'))
            keyword_filters.append(DocumentChunk.content.ilike(f'%CÓDIGO DEL COMANDO%{code}%'))
            keyword_filters.append(DocumentChunk.content.ilike(f'%VARIACIONES:%{code}%'))
        
        # Buscar por similitud semántica O por palabras clave
        if keyword_filters:
            from sqlalchemy import or_
            stmt = stmt.where(or_(*keyword_filters))
        
        # Construir expresión SQL para bonus de similitud con comandos E10B
        bonus_conditions = []
        
        # Bonus estándar para palabras clave
        for kw in keywords:
            bonus_conditions.append((DocumentChunk.content.ilike(f'%{kw}%'), 0.15))
        
        # Bonus extra alto para códigos de comando E10B exactos
        for code in command_codes:
            bonus_conditions.append((DocumentChunk.content.ilike(f'%{code}%'), 0.25))
            bonus_conditions.append((DocumentChunk.content.ilike(f'%CÓDIGO%{code}%'), 0.30))
            bonus_conditions.append((DocumentChunk.content.ilike(f'%CÓDIGO DEL COMANDO%{code}%'), 0.30))
            bonus_conditions.append((DocumentChunk.content.ilike(f'%VARIACIONES:%{code}%'), 0.30))
        
        bonus_case = (
            case(
                *bonus_conditions,
                else_=0
            )
        )
        
        # Calcular similitud con bonus en SQL
        similarity_with_bonus = (1 - func.abs(DocumentChunk.embedding.cosine_distance(query_embedding))) + bonus_case
        
        stmt = stmt.order_by(similarity_with_bonus.desc()).limit(top_k * 3)  # 🔥 Permite más resultados para filtering
        
        rows = db.execute(stmt).all()
        
        print(f"🔍 Resultados brutos de DB: {len(rows)}")
        
        # Formatear resultados directamente sin bucles adicionales
        results = []
        for chunk, filename, metadata, similarity in rows:
            # 🔥 Reducido threshold de 0.5 a 0.30 para capturar más coincidencias
            if similarity > 0.30:
                results.append({
                    "content": chunk.content,
                    "filename": filename,
                    "similarity": min(1.0, similarity),  # Asegurar máximo 1.0
                    "metadata": metadata
                })

        return results[:top_k]  # Ya ordenados por SQL

    # =========================
    # ANSWER (SIN CAMBIOS MAYORES)
    # =========================
    @staticmethod
    async def answer_question(
        db: Session, 
        question: str, 
        top_k: int = 5,
        conversation_context: List[Dict] = None
    ):

        chunks = await RAGService.search(db, question, top_k)

        if not chunks:
            return {
                "answer": "No encontré información relevante.",
                "has_context": False,
                "sources": []
            }

        context = "\n\n---\n\n".join([
            f"[{c['filename']}]\n{c['content']}"
            for c in chunks
        ])

        # Construir prompt con contexto conversacional si existe
        conversation_history = ""
        if conversation_context:
            conversation_history = "\n\nHISTORIAL DE CONVERSACIÓN:\n"
            for msg in conversation_context:
                role = "Usuario" if msg["role"] == "user" else "Asistente"
                conversation_history += f"{role}: {msg['content']}\n"

        # Detectar tipo de pregunta para adaptar la respuesta
        question_lower = question.lower()
        question_type = ""
        if "qué hace" in question_lower or "para qué sirve" in question_lower or "para que se usa" in question_lower:
            question_type = "función"
        elif "qué comando" in question_lower or "cuál comando" in question_lower or "qué comando se utiliza" in question_lower:
            question_type = "identificación"
        elif "parámetro" in question_lower or "parámetros" in question_lower or "argumento" in question_lower:
            question_type = "parámetros"
        elif "ejemplo" in question_lower or "cómo se lanza" in question_lower or "cómo se usa" in question_lower:
            question_type = "ejemplo"
        elif "significa" in question_lower or "qué significa" in question_lower:
            question_type = "interpretación"

        prompt = f"""
            Eres un experto en telecomunicaciones y operador de central telefónica E10B.
            
            {conversation_history}
            
            INSTRUCCIONES CRÍTICAS - LEER ATENTAMENTE:
            
            1. VERIFICACIÓN OBLIGATORIA DE FUNCIÓN:
               - ANTES de responder, verifica que el comando seleccionado REALMENTE realiza la función solicitada
               - Compara la descripción del comando (campo "COMANDO:") con la pregunta del usuario
               - Si la descripción NO coincide con la función solicitada, busca otro comando en el contexto
               - Si NINGÚN comando en el contexto realiza la función solicitada, indica claramente: "No encontré un comando que realice esa función específica"
            
            2. ESTRUCTURA DE LOS DATOS:
               - "COMANDO:" = descripción de la acción que realiza el comando
               - "CÓDIGO:" = código técnico del comando (ej: ABOCR-01, ACHCR-01)
               - "FUNCIÓN:" = función técnica específica
               - "VARIACIONES:" = códigos alternativos del mismo comando
            
            3. REGLAS DE RESPUESTA:
               - Responde EXCLUSIVAMENTE con la información del contexto proporcionado
               - NUNCA inventes comandos o códigos que no estén en el contexto
               - Si hay múltiples comandos relacionados, menciona TODOS los relevantes del contexto
               - Si la pregunta pide parámetros o ejemplos y el contexto no los tiene, indícalo claramente
            
            4. ADAPTACIÓN AL TIPO DE PREGUNTA:
               - Pregunta sobre FUNCIÓN: Explica qué hace el comando y su propósito
               - Pregunta sobre IDENTIFICACIÓN: Indica qué comando se usa para la acción solicitada
               - Pregunta sobre PARÁMETROS: Lista los parámetros mencionados en el contexto
               - Pregunta sobre EJEMPLO: Muestra el ejemplo de lanzamiento si está disponible
               - Pregunta sobre INTERPRETACIÓN: Explica el significado de la respuesta según el contexto
            
            CONTEXTO DISPONIBLE:
            {context}
            
            PREGUNTA DEL USUARIO:
            {question}
            
            Tipo de pregunta detectado: {question_type if question_type else "general"}
            
            TU RESPUESTA:
        """

        print(prompt)

        answer = await llm_service.chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.1  # Más bajo para respuestas más deterministas y precisas
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