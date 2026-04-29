from fastapi import APIRouter, HTTPException
from datetime import datetime
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service
from app.core.metrics import ai_metrics
from app.core.ai_logger import ai_logger

router = APIRouter(tags=["health"])

async def check_database() -> dict:
    """Verificar conexión a base de datos"""
    try:
        # Simple query para verificar conexión
        async for db in get_db():
            await db.execute("SELECT 1")
            return {"status": "healthy", "message": "Database connection OK"}
    except Exception as e:
        ai_logger.logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "message": f"Database connection failed: {str(e)}"}

async def check_ollama() -> dict:
    """Verificar conexión a Ollama"""
    try:
        # Intentar hacer una petición simple a Ollama
        test_messages = [{"role": "user", "content": "test"}]
        response = await llm_service.chat_completion(test_messages, max_tokens=10)
        return {"status": "healthy", "message": "Ollama connection OK", "model": settings.LLM_MODEL}
    except Exception as e:
        ai_logger.logger.error(f"Ollama health check failed: {e}")
        return {"status": "unhealthy", "message": f"Ollama connection failed: {str(e)}"}

async def check_embeddings() -> dict:
    """Verificar servicio de embeddings"""
    try:
        # Intentar generar embedding de texto simple
        test_text = "test embedding"
        embedding = await embedding_service.get_embedding(test_text)
        if len(embedding) > 0:
            return {
                "status": "healthy", 
                "message": "Embedding service OK", 
                "model": settings.EMBEDDING_MODEL,
                "embedding_dim": len(embedding)
            }
        else:
            return {"status": "unhealthy", "message": "Embedding service returned empty result"}
    except Exception as e:
        ai_logger.logger.error(f"Embedding health check failed: {e}")
        return {"status": "unhealthy", "message": f"Embedding service failed: {str(e)}"}

async def check_redis() -> dict:
    """Verificar conexión a Redis"""
    try:
        health = await cache_manager.health_check()
        return health
    except Exception as e:
        ai_logger.logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "message": f"Redis connection failed: {str(e)}"}

async def check_memory_usage() -> dict:
    """Verificar uso de memoria"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return {
            "status": "healthy",
            "message": "Memory check OK",
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent_used": memory.percent,
            "warning_threshold": memory.percent > 80
        }
    except ImportError:
        return {"status": "unknown", "message": "psutil not installed"}
    except Exception as e:
        return {"status": "unhealthy", "message": f"Memory check failed: {str(e)}"}

async def check_disk_space() -> dict:
    """Verificar espacio en disco"""
    try:
        import psutil
        disk = psutil.disk_usage('/')
        return {
            "status": "healthy",
            "message": "Disk space check OK",
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": round((disk.total - disk.free) / disk.total * 100, 2),
            "warning_threshold": (disk.total - disk.free) / disk.total > 0.8
        }
    except ImportError:
        return {"status": "unknown", "message": "psutil not installed"}
    except Exception as e:
        return {"status": "unhealthy", "message": f"Disk check failed: {str(e)}"}

@router.get("/health")
async def health_check():
    """Health check básico"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": settings.PROJECT_NAME
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Health check detallado de todos los componentes"""
    start_time = asyncio.get_event_loop().time()
    
    # Ejecutar todos los checks en paralelo
    checks = await asyncio.gather(
        check_database(),
        check_ollama(),
        check_embeddings(),
        check_redis(),
        check_memory_usage(),
        check_disk_space(),
        return_exceptions=True
    )
    
    duration = asyncio.get_event_loop().time() - start_time
    
    # Procesar resultados
    results = {
        "overall_status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": settings.PROJECT_NAME,
        "duration_ms": round(duration * 1000, 2),
        "components": {
            "database": checks[0] if not isinstance(checks[0], Exception) else {"status": "error", "message": str(checks[0])},
            "ollama": checks[1] if not isinstance(checks[1], Exception) else {"status": "error", "message": str(checks[1])},
            "embeddings": checks[2] if not isinstance(checks[2], Exception) else {"status": "error", "message": str(checks[2])},
            "redis": checks[3] if not isinstance(checks[3], Exception) else {"status": "error", "message": str(checks[3])},
            "memory": checks[4] if not isinstance(checks[4], Exception) else {"status": "error", "message": str(checks[4])},
            "disk": checks[5] if not isinstance(checks[5], Exception) else {"status": "error", "message": str(checks[5])}
        }
    }
    
    # Determinar estado general
    unhealthy_components = []
    for name, check in results["components"].items():
        if check.get("status") in ["unhealthy", "error"]:
            unhealthy_components.append(name)
        elif check.get("warning_threshold"):
            results["overall_status"] = "degraded"
    
    if unhealthy_components:
        results["overall_status"] = "unhealthy"
        results["unhealthy_components"] = unhealthy_components
    
    # Agregar métricas básicas
    try:
        metrics_summary = ai_metrics.get_all_metrics()
        results["metrics_summary"] = {
            "total_requests": metrics_summary["counters"].get("rag_operations_total", 0),
            "total_inferences": metrics_summary["counters"].get("model_inferences_total", 0),
            "active_models": len(metrics_summary["model_metrics"])
        }
    except Exception as e:
        results["metrics_summary"] = {"error": str(e)}
    
    return results

@router.get("/health/ready")
async def readiness_check():
    """Readiness check para Kubernetes/orquestación"""
    detailed = await detailed_health_check()
    
    # Considerar "ready" solo si todos los componentes críticos están healthy
    critical_components = ["database", "ollama", "embeddings", "redis"]
    
    for component in critical_components:
        comp_status = detailed["components"].get(component, {}).get("status")
        if comp_status in ["unhealthy", "error"]:
            raise HTTPException(
                status_code=503,
                detail=f"Service not ready: {component} is {comp_status}"
            )
    
    return {
        "status": "ready",
        "timestamp": datetime.now().isoformat(),
        "components_checked": critical_components
    }

@router.get("/health/live")
async def liveness_check():
    """Liveness check para Kubernetes/orquestación"""
    # Liveness es más simple - solo verifica que el proceso está vivo
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "uptime": "process_running"
    }