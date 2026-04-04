from openai import AsyncOpenAI
from app.core.config import settings
from typing import List
import tiktoken


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY

        )
        self.model = settings.EMBEDDING_MODEL
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Obtener embeddings para una lista de textos"""
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]

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