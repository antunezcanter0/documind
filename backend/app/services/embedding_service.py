from openai import AsyncOpenAI
from app.core.config import settings
from app.core.ai_logger import ai_logger, log_embedding_operation
from app.core.metrics import ai_metrics
from app.core.cache import cache_manager, cache_embedding
from typing import List
import tiktoken


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0
        )
        self.model = settings.EMBEDDING_MODEL
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    @cache_embedding()
    @log_embedding_operation(model_name="nomic-embed-text")
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Obtener embeddings para una lista de textos"""
        import time
        start_time = time.time()
        success = True
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            # Registrar métricas
            duration = time.time() - start_time
            text_length = sum(len(text) for text in texts)
            chunk_count = len(texts)
            
            ai_metrics.record_embedding_operation(
                model_name=self.model,
                text_length=text_length,
                chunk_count=chunk_count,
                duration=duration,
                success=success
            )
            
            return [item.embedding for item in response.data]
            
        except Exception as e:
            duration = time.time() - start_time
            text_length = sum(len(text) for text in texts)
            chunk_count = len(texts)
            
            ai_metrics.record_embedding_operation(
                model_name=self.model,
                text_length=text_length,
                chunk_count=chunk_count,
                duration=duration,
                success=False
            )
            raise

    async def get_embedding(self, text: str) -> List[float]:
        """Obtener embedding para un solo texto"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0]

    def count_tokens(self, text: str) -> int:
        """Contar tokens para control de costos"""
        return len(self.tokenizer.encode(text))

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Dividir texto en chunks para procesar"""
        tokens = self.tokenizer.encode(text)
        chunks = []

        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks


embedding_service = EmbeddingService()