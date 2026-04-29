# tests/conftest.py
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from app.main import app
from app.core.config import settings
from app.core.database import get_db, Base
from app.models.document import Document, DocumentChunk

# Configuración de test database
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/documind", "/test_documind")

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def test_session(test_engine):
    """Create test database session"""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session

@pytest.fixture
def test_client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
async def async_client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def override_db(test_session):
    """Override database dependency"""
    async def get_test_db():
        yield test_session
    
    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def sample_document(test_session):
    """Create sample document for testing"""
    doc = Document(
        filename="test.pdf",
        content="This is a test document content for AI engineering testing.",
        content_hash="test_hash_123",
        file_type="pdf",
        chunk_count=2,
        doc_metadata={"source": "test"}
    )
    test_session.add(doc)
    await test_session.commit()
    await test_session.refresh(doc)
    
    # Add chunks
    chunk1 = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="This is a test document content",
        embedding=[0.1] * 768  # Dummy embedding
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        chunk_index=1,
        content="for AI engineering testing",
        embedding=[0.2] * 768  # Dummy embedding
    )
    test_session.add_all([chunk1, chunk2])
    await test_session.commit()
    
    return doc

@pytest.fixture
def mock_ollama_response():
    """Mock response for Ollama API"""
    return {
        "choices": [{
            "message": {
                "content": "This is a test response from the AI model."
            }
        }]
    }

@pytest.fixture
def mock_embedding_response():
    """Mock response for embedding API"""
    return {
        "data": [{
            "embedding": [0.1] * 768  # 768-dimensional embedding
        }]
    }

# Test utilities
async def create_test_document(session, filename="test.txt", content="Test content"):
    """Helper to create test documents"""
    doc = Document(
        filename=filename,
        content=content,
        content_hash=f"hash_{filename}",
        file_type="txt",
        chunk_count=1
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc

# Mock fixtures for external services
@pytest.fixture
def mock_embedding_service(mocker):
    """Mock embedding service"""
    mock = mocker.patch('app.services.embedding_service.embedding_service')
    mock.get_embedding.return_value = [0.1] * 768
    mock.get_embeddings.return_value = [[0.1] * 768, [0.2] * 768]
    mock.chunk_text.return_value = ["chunk1", "chunk2"]
    return mock

@pytest.fixture
def mock_llm_service(mocker):
    """Mock LLM service"""
    mock = mocker.patch('app.services.llm_service.llm_service')
    mock.chat_completion.return_value = "Test AI response"
    return mock

@pytest.fixture
def mock_rag_service(mocker):
    """Mock RAG service"""
    mock = mocker.patch('app.services.rag_service.rag_service')
    mock.search.return_value = [
        {
            "chunk_id": "test-chunk-1",
            "document_id": "test-doc-1",
            "filename": "test.pdf",
            "content": "Test chunk content",
            "similarity": 0.85,
            "chunk_index": 0,
            "metadata": {}
        }
    ]
    mock.answer_question.return_value = {
        "answer": "Test answer",
        "sources": [{"filename": "test.pdf", "similarity": 0.85}],
        "has_context": True,
        "chunks_used": 1
    }
    return mock
