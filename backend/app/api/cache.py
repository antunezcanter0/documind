# app/api/cache.py
from fastapi import APIRouter, HTTPException
from app.core.cache import cache_manager
from app.core.ai_logger import ai_logger
from typing import Dict, Any

router = APIRouter(prefix="/cache", tags=["cache"])

@router.get("/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Obtener estadísticas del caché Redis"""
    try:
        stats = await cache_manager.get_cache_stats()
        return stats
    except Exception as e:
        ai_logger.logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving cache stats")

@router.get("/health")
async def cache_health_check() -> Dict[str, Any]:
    """Health check del caché Redis"""
    try:
        health = await cache_manager.health_check()
        return health
    except Exception as e:
        ai_logger.logger.error(f"Error in cache health check: {e}")
        raise HTTPException(status_code=500, detail="Cache health check failed")

@router.delete("/clear")
async def clear_cache(pattern: str = "*") -> Dict[str, str]:
    """Limpiar caché por patrón"""
    try:
        deleted_count = await cache_manager.clear_pattern(pattern)
        ai_logger.logger.info(f"Cache cleared: {deleted_count} keys deleted")
        return {"message": f"Cache cleared successfully", "keys_deleted": str(deleted_count)}
    except Exception as e:
        ai_logger.logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Error clearing cache")

@router.delete("/clear/embeddings")
async def clear_embedding_cache() -> Dict[str, str]:
    """Limpiar caché de embeddings"""
    try:
        deleted_count = await cache_manager.clear_pattern("embedding:*")
        ai_logger.logger.info(f"Embedding cache cleared: {deleted_count} keys deleted")
        return {"message": "Embedding cache cleared", "keys_deleted": str(deleted_count)}
    except Exception as e:
        ai_logger.logger.error(f"Error clearing embedding cache: {e}")
        raise HTTPException(status_code=500, detail="Error clearing embedding cache")

@router.delete("/clear/llm")
async def clear_llm_cache() -> Dict[str, str]:
    """Limpiar caché de LLM"""
    try:
        deleted_count = await cache_manager.clear_pattern("llm:*")
        ai_logger.logger.info(f"LLM cache cleared: {deleted_count} keys deleted")
        return {"message": "LLM cache cleared", "keys_deleted": str(deleted_count)}
    except Exception as e:
        ai_logger.logger.error(f"Error clearing LLM cache: {e}")
        raise HTTPException(status_code=500, detail="Error clearing LLM cache")

@router.delete("/clear/rag")
async def clear_rag_cache() -> Dict[str, str]:
    """Limpiar caché de RAG"""
    try:
        deleted_count = await cache_manager.clear_pattern("rag:*")
        ai_logger.logger.info(f"RAG cache cleared: {deleted_count} keys deleted")
        return {"message": "RAG cache cleared", "keys_deleted": str(deleted_count)}
    except Exception as e:
        ai_logger.logger.error(f"Error clearing RAG cache: {e}")
        raise HTTPException(status_code=500, detail="Error clearing RAG cache")
