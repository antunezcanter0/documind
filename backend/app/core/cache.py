# app/core/cache_simple.py
import json
import hashlib
import pickle
from typing import Any, Optional, Union, List
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from app.core.config import settings

class CacheManager:
    """Gestor de caché Redis simplificado"""
    
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
            print("Connected to Redis successfully")
            
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Desconectar de Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print("Disconnected from Redis")
    
    def _generate_key(self, prefix: str, data: Union[str, dict, list]) -> str:
        """Genera clave de caché basada en datos"""
        if isinstance(data, (dict, list)):
            # Serializar para clave consistente
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        
        # Hash para claves largas
        if len(data_str) > 100:
            data_hash = hashlib.md5(data_str.encode()).hexdigest()
            return f"{prefix}:{data_hash}"
        else:
            return f"{prefix}:{data_str}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché"""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value is not None:
                # Deserializar
                return pickle.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Establecer valor en caché"""
        if not self.redis_client:
            return False
        
        try:
            # Serializar
            serialized_value = pickle.dumps(value)
            
            if ttl:
                await self.redis_client.setex(key, ttl, serialized_value)
            else:
                await self.redis_client.set(key, serialized_value)
            
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Eliminar clave del caché"""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Limpiar claves por patrón"""
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
            return len(keys)
        except Exception as e:
            print(f"Cache clear pattern error: {e}")
            return 0
    
    async def get_cache_stats(self) -> dict:
        """Obtener estadísticas del caché"""
        if not self.redis_client:
            return {"status": "disconnected"}
        
        try:
            info = await self.redis_client.info()
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            print(f"Cache stats error: {e}")
            return {"status": "error", "error": str(e)}
    
    def _calculate_hit_rate(self, info: dict) -> float:
        """Calcular hit rate"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
    
    async def health_check(self) -> dict:
        """Health check del caché"""
        try:
            if not self.redis_client:
                await self.connect()
            
            await self.redis_client.ping()
            stats = await self.get_cache_stats()
            
            return {
                "status": "healthy",
                "message": "Redis connection OK",
                "timestamp": datetime.utcnow().isoformat(),
                "stats": stats
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

# Instancia global
cache_manager = CacheManager()

# Decorators simplificados
def cache_embedding(ttl: Optional[int] = None):
    """Decorator para caché de embeddings"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generar clave
            cache_key = cache_manager._generate_key("embedding", args[1] if len(args) > 1 else "")
            
            # Intentar obtener del caché
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función
            result = await func(*args, **kwargs)
            
            # Cachear resultado
            cache_ttl = ttl or 3600  # 1 hora por defecto
            await cache_manager.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator

def cache_llm_response(ttl: Optional[int] = None):
    """Decorator para caché de respuestas LLM"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generar clave
            cache_key = cache_manager._generate_key("llm", {
                "messages": args[1] if len(args) > 1 else [],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1000)
            })
            
            # Intentar obtener del caché
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función
            result = await func(*args, **kwargs)
            
            # Cachear resultado
            cache_ttl = ttl or 600  # 10 minutos por defecto
            await cache_manager.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator

def cache_rag_response(ttl: Optional[int] = None):
    """Decorator para caché de respuestas RAG"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generar clave
            cache_key = cache_manager._generate_key("rag", {
                "question": args[1] if len(args) > 1 else "",
                "top_k": kwargs.get("top_k", 5)
            })
            
            # Intentar obtener del caché
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función
            result = await func(*args, **kwargs)
            
            # Cachear resultado
            cache_ttl = ttl or 300  # 5 minutos por defecto
            await cache_manager.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator
