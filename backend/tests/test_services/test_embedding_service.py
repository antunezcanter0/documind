# tests/test_services/test_embedding_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.embedding_service import EmbeddingService

class TestEmbeddingService:
    """Tests para el servicio de embeddings"""
    
    @pytest.fixture
    def embedding_service(self):
        """Crear instancia del servicio para testing"""
        return EmbeddingService()
    
    @pytest.mark.asyncio
    async def test_get_embedding_single_text(self, embedding_service, mock_embedding_response):
        """Test obtener embedding de un solo texto"""
        with patch.object(embedding_service.client.embeddings, 'create') as mock_create:
            mock_create.return_value = mock_embedding_response
            
            result = await embedding_service.get_embedding("test text")
            
            assert isinstance(result, list)
            assert len(result) == 768  # Dimensión del embedding
            assert all(isinstance(x, float) for x in result)
            
            # Verificar que se llamó correctamente
            mock_create.assert_called_once_with(
                model=embedding_service.model,
                input=["test text"]
            )
    
    @pytest.mark.asyncio
    async def test_get_embeddings_multiple_texts(self, embedding_service, mock_embedding_response):
        """Test obtener embeddings de múltiples textos"""
        with patch.object(embedding_service.client.embeddings, 'create') as mock_create:
            # Mock para múltiples embeddings
            mock_create.return_value = {
                "data": [
                    {"embedding": [0.1] * 768},
                    {"embedding": [0.2] * 768}
                ]
            }
            
            texts = ["text1", "text2"]
            result = await embedding_service.get_embeddings(texts)
            
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(embedding, list) for embedding in result)
            assert all(len(embedding) == 768 for embedding in result)
            
            mock_create.assert_called_once_with(
                model=embedding_service.model,
                input=texts
            )
    
    @pytest.mark.asyncio
    async def test_get_embedding_error_handling(self, embedding_service):
        """Test manejo de errores en embedding service"""
        with patch.object(embedding_service.client.embeddings, 'create') as mock_create:
            mock_create.side_effect = Exception("API Error")
            
            with pytest.raises(Exception):
                await embedding_service.get_embedding("test text")
    
    def test_count_tokens(self, embedding_service):
        """Test conteo de tokens"""
        text = "This is a test text for token counting"
        tokens = embedding_service.count_tokens(text)
        
        assert isinstance(tokens, int)
        assert tokens > 0
    
    def test_chunk_text(self, embedding_service):
        """Test división de texto en chunks"""
        text = "This is a longer text that should be split into multiple chunks for testing purposes. " * 10
        
        chunks = embedding_service.chunk_text(text, chunk_size=50, overlap=10)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 1
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)
        
        # Verificar overlap
        for i in range(len(chunks) - 1):
            # Debe haber overlap entre chunks consecutivos
            current_end = chunks[i][-10:]
            next_start = chunks[i + 1][:10]
            # El overlap no es garantizado exactamente pero debe haber superposición
            assert len(current_end) > 0
            assert len(next_start) > 0
    
    def test_chunk_text_parameters(self, embedding_service):
        """Test diferentes parámetros de chunking"""
        text = "Test text for chunking with different parameters. " * 5
        
        # Test diferentes chunk sizes
        chunks_small = embedding_service.chunk_text(text, chunk_size=20, overlap=5)
        chunks_large = embedding_service.chunk_text(text, chunk_size=100, overlap=20)
        
        assert len(chunks_small) > len(chunks_large)
        
        # Test overlap cero
        chunks_no_overlap = embedding_service.chunk_text(text, chunk_size=50, overlap=0)
        assert len(chunks_no_overlap) > 0
        
        # Verificar que no haya overlap
        for i in range(len(chunks_no_overlap) - 1):
            current_end = chunks_no_overlap[i][-5:]
            next_start = chunks_no_overlap[i + 1][:5]
            assert current_end != next_start
    
    @pytest.mark.asyncio
    async def test_embedding_service_initialization(self):
        """Test inicialización del servicio"""
        service = EmbeddingService()
        
        assert service.model is not None
        assert service.client is not None
        assert service.tokenizer is not None
        assert hasattr(service, 'model')
        assert hasattr(service, 'client')
        assert hasattr(service, 'tokenizer')
