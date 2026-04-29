# tests/test_api/test_health.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

class TestHealthAPI:
    """Tests para health check endpoints"""
    
    def test_health_basic(self, test_client: TestClient):
        """Test health check básico"""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"
        assert data["service"] == "DocuMind"
    
    @pytest.mark.asyncio
    async def test_health_detailed(self, async_client: AsyncClient, override_db):
        """Test health check detallado"""
        response = await async_client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert "overall_status" in data
        assert "timestamp" in data
        assert "components" in data
        assert "duration_ms" in data
        
        # Verificar componentes
        components = data["components"]
        assert "database" in components
        assert "ollama" in components
        assert "embeddings" in components
        assert "memory" in components
        assert "disk" in components
        
        # Cada componente debe tener status
        for component in components.values():
            assert "status" in component
    
    @pytest.mark.asyncio
    async def test_health_ready(self, async_client: AsyncClient, override_db):
        """Test readiness check"""
        response = await async_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "components_checked" in data
    
    @pytest.mark.asyncio
    async def test_health_live(self, async_client: AsyncClient):
        """Test liveness check"""
        response = await async_client.get("/api/v1/health/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    def test_health_response_structure(self, test_client: TestClient):
        """Test estructura de respuesta de health check"""
        response = test_client.get("/api/v1/health")
        data = response.json()
        
        # Verificar campos obligatorios
        required_fields = ["status", "timestamp", "version", "service"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verificar tipos de datos
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["service"], str)
