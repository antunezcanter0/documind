# tests/test_integration/test_chat_api.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch

class TestChatAPIIntegration:
    """Tests de integración para la API de chat"""
    
    @pytest.mark.asyncio
    async def test_chat_ask_endpoint(self, async_client: AsyncClient, override_db, sample_document, mock_rag_service):
        """Test endpoint de chat con RAG"""
        with patch('app.api.chat.rag_service', mock_rag_service):
            request_data = {
                "question": "What is this document about?",
                "use_rag": True,
                "top_k": 3
            }
            
            response = await async_client.post("/api/v1/chat/ask", json=request_data)
            
            assert response.status_code == 200
            
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert "has_context" in data
            assert "chunks_used" in data
            
            assert data["has_context"] is True
            assert isinstance(data["answer"], str)
            assert isinstance(data["sources"], list)
    
    @pytest.mark.asyncio
    async def test_chat_ask_without_rag(self, async_client: AsyncClient, mock_llm_service):
        """Test endpoint de chat sin RAG"""
        with patch('app.api.chat.llm_service', mock_llm_service):
            request_data = {
                "question": "Tell me a joke",
                "use_rag": False,
                "top_k": 3
            }
            
            response = await async_client.post("/api/v1/chat/ask", json=request_data)
            
            assert response.status_code == 200
            
            data = response.json()
            assert data["has_context"] is False
            assert data["sources"] == []
            assert data["chunks_used"] is None
    
    @pytest.mark.asyncio
    async def test_chat_search_endpoint(self, async_client: AsyncClient, override_db, sample_document, mock_rag_service):
        """Test endpoint de búsqueda de documentos"""
        with patch('app.api.chat.rag_service', mock_rag_service):
            request_data = {
                "query": "test search",
                "top_k": 5
            }
            
            response = await async_client.post("/api/v1/chat/search", json=request_data)
            
            assert response.status_code == 200
            
            data = response.json()
            assert "results" in data
            assert "count" in data
            
            assert isinstance(data["results"], list)
            assert isinstance(data["count"], int)
            assert data["count"] == len(data["results"])
    
    @pytest.mark.asyncio
    async def test_chat_ask_validation(self, async_client: AsyncClient):
        """Test validación de inputs en chat endpoint"""
        # Test sin pregunta
        request_data = {
            "question": "",
            "use_rag": True,
            "top_k": 3
        }
        
        response = await async_client.post("/api/v1/chat/ask", json=request_data)
        
        # FastAPI debería manejar validación automáticamente
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_ask_invalid_top_k(self, async_client: AsyncClient):
        """Test validación de top_k"""
        request_data = {
            "question": "Test question",
            "use_rag": True,
            "top_k": -1  # Valor inválido
        }
        
        response = await async_client.post("/api/v1/chat/ask", json=request_data)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_chat_search_validation(self, async_client: AsyncClient):
        """Test validación en search endpoint"""
        # Test sin query
        request_data = {
            "query": "",
            "top_k": 5
        }
        
        response = await async_client.post("/api/v1/chat/search", json=request_data)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_chat_error_handling(self, async_client: AsyncClient, override_db):
        """Test manejo de errores en chat API"""
        # Mock que lanza error
        with patch('app.api.chat.rag_service') as mock_rag:
            mock_rag.answer_question.side_effect = Exception("RAG Service Error")
            
            request_data = {
                "question": "Test question",
                "use_rag": True,
                "top_k": 3
            }
            
            response = await async_client.post("/api/v1/chat/ask", json=request_data)
            assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_chat_concurrent_requests(self, async_client: AsyncClient, override_db, sample_document, mock_rag_service):
        """Test múltiples peticiones concurrentes"""
        import asyncio
        
        with patch('app.api.chat.rag_service', mock_rag_service):
            # Crear múltiples peticiones concurrentes
            requests = [
                {
                    "question": f"Test question {i}",
                    "use_rag": True,
                    "top_k": 3
                }
                for i in range(5)
            ]
            
            tasks = [
                async_client.post("/api/v1/chat/ask", json=req)
                for req in requests
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            assert len(responses) == 5
            
            # Verificar que todas las respuestas sean exitosas
            for response in responses:
                if not isinstance(response, Exception):
                    assert response.status_code == 200
                    data = response.json()
                    assert "answer" in data
    
    @pytest.mark.asyncio
    async def test_chat_response_structure(self, async_client: AsyncClient, override_db, sample_document, mock_rag_service):
        """Test estructura de respuesta de chat"""
        with patch('app.api.chat.rag_service', mock_rag_service):
            request_data = {
                "question": "Test question structure",
                "use_rag": True,
                "top_k": 3
            }
            
            response = await async_client.post("/api/v1/chat/ask", json=request_data)
            assert response.status_code == 200
            
            data = response.json()
            
            # Verificar campos obligatorios
            required_fields = ["answer", "sources", "has_context", "chunks_used"]
            for field in required_fields:
                assert field in data, f"Missing field: {field}"
            
            # Verificar tipos de datos
            assert isinstance(data["answer"], str)
            assert isinstance(data["sources"], list)
            assert isinstance(data["has_context"], bool)
            assert data["chunks_used"] is None or isinstance(data["chunks_used"], int)
            
            # Si hay contexto, verificar fuentes
            if data["has_context"]:
                assert len(data["sources"]) > 0
                assert data["chunks_used"] is not None
                assert data["chunks_used"] > 0
                
                # Verificar estructura de fuentes
                for source in data["sources"]:
                    assert "filename" in source
                    assert "similarity" in source
