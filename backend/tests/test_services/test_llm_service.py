# tests/test_services/test_llm_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_service import LLMService

class TestLLMService:
    """Tests para el servicio LLM"""
    
    @pytest.fixture
    def llm_service(self):
        """Crear instancia del servicio para testing"""
        return LLMService()
    
    @pytest.mark.asyncio
    async def test_chat_completion(self, llm_service, mock_ollama_response):
        """Test chat completion básico"""
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_ollama_response
            
            messages = [{"role": "user", "content": "Hello, how are you?"}]
            result = await llm_service.chat_completion(messages)
            
            assert isinstance(result, str)
            assert len(result) > 0
            assert result == "This is a test response from the AI model."
            
            # Verificar que se llamó correctamente
            mock_create.assert_called_once_with(
                model=llm_service.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
    
    @pytest.mark.asyncio
    async def test_chat_completion_with_parameters(self, llm_service, mock_ollama_response):
        """Test chat completion con parámetros personalizados"""
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_ollama_response
            
            messages = [{"role": "user", "content": "Test message"}]
            result = await llm_service.chat_completion(
                messages, 
                temperature=0.5, 
                max_tokens=500
            )
            
            assert isinstance(result, str)
            
            mock_create.assert_called_once_with(
                model=llm_service.model,
                messages=messages,
                temperature=0.5,
                max_tokens=500
            )
    
    @pytest.mark.asyncio
    async def test_stream_chat_completion(self, llm_service):
        """Test streaming chat completion"""
        # Mock streaming response
        async def mock_stream():
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " world"}}]},
                {"choices": [{"delta": {"content": "!"}}]}
            ]
            for chunk in chunks:
                yield chunk
        
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_stream()
            
            messages = [{"role": "user", "content": "Say hello"}]
            
            # Collect streamed response
            result_parts = []
            async for chunk in llm_service.stream_chat_completion(messages):
                result_parts.append(chunk)
            
            result = "".join(result_parts)
            assert result == "Hello world!"
            
            mock_create.assert_called_once_with(
                model=llm_service.model,
                messages=messages,
                temperature=0.7,
                stream=True
            )
    
    @pytest.mark.asyncio
    async def test_chat_completion_error_handling(self, llm_service):
        """Test manejo de errores en LLM service"""
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = Exception("LLM API Error")
            
            messages = [{"role": "user", "content": "Test"}]
            
            with pytest.raises(Exception):
                await llm_service.chat_completion(messages)
    
    @pytest.mark.asyncio
    async def test_stream_chat_completion_error_handling(self, llm_service):
        """Test manejo de errores en streaming"""
        async def mock_stream_error():
            raise Exception("Streaming error")
        
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_stream_error()
            
            messages = [{"role": "user", "content": "Test"}]
            
            with pytest.raises(Exception):
                async for _ in llm_service.stream_chat_completion(messages):
                    pass
    
    @pytest.mark.asyncio
    async def test_chat_completion_empty_response(self, llm_service):
        """Test respuesta vacía del LLM"""
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = {
                "choices": [{"message": {"content": ""}}]
            }
            
            messages = [{"role": "user", "content": "Test"}]
            result = await llm_service.chat_completion(messages)
            
            assert result == ""
    
    @pytest.mark.asyncio
    async def test_chat_completion_long_message(self, llm_service, mock_ollama_response):
        """Test con mensaje largo"""
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_ollama_response
            
            # Mensaje muy largo
            long_message = "This is a very long message " * 100
            messages = [{"role": "user", "content": long_message}]
            
            result = await llm_service.chat_completion(messages)
            
            assert isinstance(result, str)
            mock_create.assert_called_once()
    
    def test_llm_service_initialization(self):
        """Test inicialización del servicio"""
        service = LLMService()
        
        assert service.model is not None
        assert service.client is not None
        assert hasattr(service, 'model')
        assert hasattr(service, 'client')
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, llm_service, mock_ollama_response):
        """Test múltiples peticiones concurrentes"""
        import asyncio
        
        with patch.object(llm_service.client.chat.completions, 'create') as mock_create:
            mock_create.return_value = mock_ollama_response
            
            # Crear múltiples peticiones concurrentes
            messages = [{"role": "user", "content": f"Test message {i}"} for i in range(5)]
            
            tasks = [
                llm_service.chat_completion(msg) 
                for msg in messages
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all(isinstance(result, str) for result in results)
            assert all(result == "This is a test response from the AI model." for result in results)
