# app/services/llm_service.py
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.ai_logger import ai_logger, log_model_inference
from app.core.cache import cache_manager, cache_llm_response
from typing import List, Dict, Any, AsyncGenerator

class LLMService:
    def __init__(self):
        # Apuntamos a nuestro servidor local de Ollama
        self.client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY
        )
        self.model = settings.LLM_MODEL

    @cache_llm_response()
    @log_model_inference(model_name="llama3.2:3b")
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Chat completion usando el modelo local de Ollama"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streaming de respuestas con el modelo local"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

llm_service = LLMService()