# tests/test_services/test_rag_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.rag_service import RAGService
from app.models.document import Document, DocumentChunk

class TestRAGService:
    """Tests para el servicio RAG"""
    
    @pytest.mark.asyncio
    async def test_index_document(self, test_session, mock_embedding_service):
        """Test indexación de documento"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            filename = "test_document.txt"
            content = "This is a test document for RAG indexing."
            file_type = "txt"
            metadata = {"source": "test"}
            
            document_id = await RAGService.index_document(
                test_session, filename, content, file_type, metadata
            )
            
            assert document_id is not None
            
            # Verificar que el documento fue guardado
            from sqlalchemy import select
            doc_result = await test_session.execute(
                select(Document).where(Document.id == document_id)
            )
            document = doc_result.scalar_one()
            
            assert document.filename == filename
            assert document.content == content
            assert document.file_type == file_type
            assert document.doc_metadata == metadata
            assert document.chunk_count > 0
    
    @pytest.mark.asyncio
    async def test_index_document_duplicate(self, test_session, mock_embedding_service):
        """Test prevención de documentos duplicados"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            filename = "duplicate_test.txt"
            content = "Duplicate content test."
            
            # Primera indexación
            doc_id1 = await RAGService.index_document(
                test_session, filename, content, "txt"
            )
            
            # Segunda indexación (debería fallar)
            with pytest.raises(ValueError, match="ya fue indexado"):
                await RAGService.index_document(
                    test_session, filename, content, "txt"
                )
    
    @pytest.mark.asyncio
    async def test_search_documents(self, test_session, sample_document, mock_embedding_service):
        """Test búsqueda de documentos"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            query = "test document"
            
            results = await RAGService.search(test_session, query, top_k=5)
            
            assert isinstance(results, list)
            assert len(results) > 0
            
            # Verificar estructura de resultados
            for result in results:
                assert "chunk_id" in result
                assert "document_id" in result
                assert "filename" in result
                assert "content" in result
                assert "similarity" in result
                assert "chunk_index" in result
                assert "metadata" in result
                
                assert isinstance(result["similarity"], float)
                assert 0 <= result["similarity"] <= 1
    
    @pytest.mark.asyncio
    async def test_search_no_results(self, test_session, mock_embedding_service):
        """Test búsqueda sin resultados"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            # Query que no debería encontrar resultados
            query = "nonexistent content xyz123"
            
            results = await RAGService.search(test_session, query, top_k=5)
            
            assert isinstance(results, list)
            # Puede devolver lista vacía si no hay similitud suficiente
    
    @pytest.mark.asyncio
    async def test_answer_question_with_context(self, test_session, sample_document, mock_embedding_service, mock_llm_service):
        """Test respuesta a pregunta con contexto"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service), \
             patch('app.services.rag_service.llm_service', mock_llm_service):
            
            question = "What is this document about?"
            
            result = await RAGService.answer_question(test_session, question, top_k=3)
            
            assert "answer" in result
            assert "sources" in result
            assert "has_context" in result
            assert "chunks_used" in result
            
            assert result["has_context"] is True
            assert isinstance(result["answer"], str)
            assert len(result["answer"]) > 0
            assert isinstance(result["sources"], list)
            assert result["chunks_used"] > 0
    
    @pytest.mark.asyncio
    async def test_answer_question_no_context(self, test_session, mock_embedding_service, mock_llm_service):
        """Test respuesta a pregunta sin contexto"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service), \
             patch('app.services.rag_service.llm_service', mock_llm_service):
            
            # Mock search para no encontrar resultados
            with patch.object(RAGService, 'search', return_value=[]):
                question = "Question about nonexistent content"
                
                result = await RAGService.answer_question(test_session, question, top_k=3)
                
                assert result["has_context"] is False
                assert "No encontré información relevante" in result["answer"]
                assert result["sources"] == []
                assert result["chunks_used"] is None
    
    @pytest.mark.asyncio
    async def test_search_with_similarity_threshold(self, test_session, sample_document, mock_embedding_service):
        """Test búsqueda con umbral de similitud"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            query = "test query"
            
            # Test con umbral alto
            results_high = await RAGService.search(
                test_session, query, top_k=5, similarity_threshold=0.9
            )
            
            # Test con umbral bajo
            results_low = await RAGService.search(
                test_session, query, top_k=5, similarity_threshold=0.1
            )
            
            assert isinstance(results_high, list)
            assert isinstance(results_low, list)
            # results_low debería tener más o igual resultados que results_high
    
    @pytest.mark.asyncio
    async def test_answer_question_different_top_k(self, test_session, sample_document, mock_embedding_service, mock_llm_service):
        """Test respuesta con diferentes valores de top_k"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service), \
             patch('app.services.rag_service.llm_service', mock_llm_service):
            
            question = "Test question"
            
            # Test con top_k=1
            result_1 = await RAGService.answer_question(test_session, question, top_k=1)
            
            # Test con top_k=5
            result_5 = await RAGService.answer_question(test_session, question, top_k=5)
            
            assert result_1["chunks_used"] <= result_5["chunks_used"]
    
    @pytest.mark.asyncio
    async def test_index_document_large_content(self, test_session, mock_embedding_service):
        """Test indexación de documento con contenido grande"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            # Contenido grande que debería generar múltiples chunks
            large_content = "This is a large document content. " * 100
            
            document_id = await RAGService.index_document(
                test_session, "large_doc.txt", large_content, "txt"
            )
            
            # Verificar que se crearon múltiples chunks
            from sqlalchemy import select
            chunks_result = await test_session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            chunks = chunks_result.scalars().all()
            
            assert len(chunks) > 1
            
            # Verificar que los chunks tienen contenido y embeddings
            for chunk in chunks:
                assert len(chunk.content) > 0
                assert chunk.embedding is not None
                assert len(chunk.embedding) > 0
    
    @pytest.mark.asyncio
    async def test_search_performance(self, test_session, sample_document, mock_embedding_service):
        """Test performance de búsqueda"""
        import time
        
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            query = "performance test query"
            
            start_time = time.time()
            results = await RAGService.search(test_session, query, top_k=5)
            duration = time.time() - start_time
            
            assert isinstance(results, list)
            assert duration < 1.0  # Debería ser rápido (< 1 segundo)
    
    @pytest.mark.asyncio
    async def test_answer_question_error_handling(self, test_session, mock_embedding_service):
        """Test manejo de errores en answer_question"""
        with patch('app.services.rag_service.embedding_service', mock_embedding_service):
            # Mock LLM service que lanza error
            with patch('app.services.rag_service.llm_service') as mock_llm:
                mock_llm.chat_completion.side_effect = Exception("LLM Error")
                
                question = "Test question for error handling"
                
                with pytest.raises(Exception):
                    await RAGService.answer_question(test_session, question)
