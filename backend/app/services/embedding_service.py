import asyncio

from openai import AsyncOpenAI
from app.core.config import settings
from app.core.cache import cache_manager, cache_embedding
from typing import List
import tiktoken


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            timeout=120.0,  # ← Aumentar timeout a 120 segundos
            max_retries=3  # ← Reintentar automáticamente
        )
        self.model = settings.EMBEDDING_MODEL
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Obtener embeddings para una lista de textos con manejo de errores"""
        print(f"🔄 Iniciando embeddings para {len(texts)} textos")

        # Procesar en lotes pequeños para evitar timeouts
        batch_size = 50
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"  📦 Procesando lote {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1}")

            try:
                # Intentar con timeout
                response = await asyncio.wait_for(
                    self.client.embeddings.create(
                        model=self.model,
                        input=batch
                    ),
                    timeout=60.0  # 60 segundos por lote
                )
                all_embeddings.extend([item.embedding for item in response.data])

            except asyncio.TimeoutError:
                print(f"  ⏰ Timeout en lote, reintentando...")
                # Reintentar una vez
                try:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=batch
                    )
                    all_embeddings.extend([item.embedding for item in response.data])
                except Exception as e:
                    print(f"  ❌ Error en reintento: {e}")
                    raise
            except Exception as e:
                print(f"  ❌ Error en lote: {e}")
                raise

        print(f"✅ Embeddings completados: {len(all_embeddings)} vectores")
        return all_embeddings

    async def get_embedding(self, text: str) -> List[float]:
        """Obtener embedding para un solo texto"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def chunk_text(self, text: str, chunk_size: int = 1200, overlap: int = 200):
        tokens = self.tokenizer.encode(text)

        chunks = []
        step = chunk_size - overlap

        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks


embedding_service = EmbeddingService()