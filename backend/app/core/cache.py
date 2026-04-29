# app/core/cache.py
import json
import hashlib
import pickle
from typing import Any, Optional, Union, List
from datetime import datetime, timedelta
import aioredis
from app.core.config import settings
from app.core.ai_logger import ai_logger
from app.core.metrics import ai_metrics

class CacheManager:
    """Gestor de caché Redis para operaciones de AI/ML"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self._connection_pool = None
    
    async def connect(self):
        """Conectar a Redis"""
        try:
            self.redis_client = aioredis.from_url(
                settings.REDIS_CONNECTION_STRING,
                encoding="utf-8",
                decode_responses=False  # Para manejar datos binarios
            )
            
            # Test connection
            await self.redis_client.ping()
            ai_logger.logger.info("Connected to Redis successfully")
            
            # Registrar métricas
            ai_metrics.set_gauge("cache_connection_status", 1)
            
        except Exception as e:
            ai_logger.logger.error(f"Failed to connect to Redis: {e}")
            ai_metrics.set_gauge("cache_connection_status", 0)
            raise
    
    async def disconnect(self):
        """Desconectar de Redis"""
        if self.redis_client:
            await self.redis_client.close()
            ai_logger.logger.info("Disconnected from Redis")
            ai_metrics.set_gauge("cache_connection_status", 0)
    
    def _generate_key(self, prefix: str, data: Union[str, dict, list]) -> str:
        """Genera clave de caché basada en datos"""
        if isinstance(data, (dict, list)):
            # Serializar para clave consistente
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        
        # Hash para claves largas
        if len(data_str) > 100:
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
            return f"{prefix}:{data_hash}"
        else:
            return f"{prefix}:{data_str}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché"""
        if not self.redis_client:
            return None
        
        try:
            start_time = datetime.utcnow()
            
            # Obtener del caché
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                # Deserializar
                try:
                    value = pickle.loads(cached_data)
                    
                    # Registrar métricas
                    ai_metrics.increment_counter("cache_hits_total")
                    
                    # Log cache hit
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    ai_logger.logger.debug(f"Cache HIT: {key} in {duration:.3f}s")
                    
                    return value
                    
                except (pickle.PickleError, TypeError) as e:
                    ai_logger.logger.error(f"Cache deserialization error for key {key}: {e}")
                    return None
            else:
                # Cache miss
                ai_metrics.increment_counter("cache_misses_total")
                ai_logger.logger.debug(f"Cache MISS: {key}")
                return None
                
        except Exception as e:
            ai_logger.logger.error(f"Cache get error for key {key}: {e}")
            ai_metrics.increment_counter("cache_errors_total")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Establecer valor en caché con TTL"""
        if not self.redis_client:
            return False
        
        try:
            start_time = datetime.utcnow()
            
            # Serializar valor
            try:
                serialized_value = pickle.dumps(value)
            except (pickle.PickleError, TypeError) as e:
                ai_logger.logger.error(f"Cache serialization error for key {key}: {e}")
                return False
            
            # Establecer en caché
            await self.redis_client.setex(key, ttl, serialized_value)
            
            # Registrar métricas
            ai_metrics.increment_counter("cache_sets_total")
            
            # Log cache set
            duration = (datetime.utcnow() - start_time).total_seconds()
            ai_logger.logger.debug(f"Cache SET: {key} (TTL: {ttl}s) in {duration:.3f}s")
            
            return True
            
        except Exception as e:
            ai_logger.logger.error(f"Cache set error for key {key}: {e}")
            ai_metrics.increment_counter("cache_errors_total")
            return False
    
    async def delete(self, key: str) -> bool:
        """Eliminar clave del caché"""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(key)
            
            if result:
                ai_metrics.increment_counter("cache_deletes_total")
                ai_logger.logger.debug(f"Cache DELETE: {key}")
            
            return bool(result)
            
        except Exception as e:
            ai_logger.logger.error(f"Cache delete error for key {key}: {e}")
            ai_metrics.increment_counter("cache_errors_total")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Eliminar claves por patrón"""
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                ai_metrics.increment_counter("cache_deletes_total", deleted)
                ai_logger.logger.info(f"Cache CLEAR: {pattern} - {deleted} keys deleted")
                return deleted
            return 0
            
        except Exception as e:
            ai_logger.logger.error(f"Cache clear pattern error for {pattern}: {e}")
            ai_metrics.increment_counter("cache_errors_total")
            return 0
    
    async def get_cache_stats(self) -> dict:
        """Obtener estadísticas del caché"""
        if not self.redis_client:
            return {"connected": False}
        
        try:
            info = await self.redis_client.info()
            
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "N/A"),
                "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
            
        except Exception as e:
            ai_logger.logger.error(f"Error getting cache stats: {e}")
            return {"connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, info: dict) -> float:
        """Calcular hit rate del caché"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
    
    async def health_check(self) -> dict:
        """Health check del caché"""
        if not self.redis_client:
            return {
                "status": "unhealthy",
                "message": "Redis client not initialized"
            }
        
        try:
            # Test basic operation
            await self.redis_client.ping()
            
            # Test set/get
            test_key = "health_check_test"
            await self.redis_client.setex(test_key, 1, "test")
            value = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            if value == b"test":
                stats = await self.get_cache_stats()
                return {
                    "status": "healthy",
                    "message": "Redis connection OK",
                    "stats": stats
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "Redis read/write test failed"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Redis health check failed: {str(e)}"
            }


# Cache manager global
cache_manager = CacheManager()

# Decoradores para caché automático
def cache_embedding(ttl: int = None):
    """Decorator para cachear embeddings"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not cache_manager.redis_client:
                return await func(*args, **kwargs)
            
            # Generar clave basada en el texto
            texts = args[1] if len(args) > 1 and isinstance(args[1], list) else []
            cache_key = cache_manager._generate_key("embedding", texts)
            
            # Intentar obtener del caché
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            cache_ttl = ttl or settings.EMBEDDING_CACHE_TTL
            await cache_manager.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator

def cache_llm_response(ttl: int = None):
    """Decorator para cachear respuestas LLM"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not cache_manager.redis_client:
                return await func(*args, **kwargs)
            
            # Generar clave basada en mensajes y parámetros
            messages = args[1] if len(args) > 1 else []
            temperature = kwargs.get('temperature', 0.7)
            max_tokens = kwargs.get('max_tokens', 1000)
            
            cache_data = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            cache_key = cache_manager._generate_key("llm", cache_data)
            
            # Intentar obtener del caché
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            cache_ttl = ttl or settings.LLM_CACHE_TTL
            await cache_manager.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator

def cache_rag_response(ttl: int = None):
    """Decorator para cachear respuestas RAG"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not cache_manager.redis_client:
                return await func(*args, **kwargs)
            
            # Generar clave basada en pregunta y top_k
            question = args[1] if len(args) > 1 else ""
            top_k = args[2] if len(args) > 2 else 5
            
            cache_data = {
                "question": question,
                "top_k": top_k
            }
            cache_key = cache_manager._generate_key("rag", cache_data)
            
            # Intentar obtener del caché
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            cache_ttl = ttl or settings.RAG_CACHE_TTL
            await cache_manager.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator
