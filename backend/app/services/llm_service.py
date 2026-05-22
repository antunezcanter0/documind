# app/services/llm_service.py
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.cache import cache_manager
from typing import List, Dict, Any, AsyncGenerator

class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY
        )
        self.model = settings.LLM_MODEL

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3
    ) -> str:
        """Obtener una respuesta completa del LLM"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=False
        )
        return response.choices[0].message.content


llm_service = LLMService()