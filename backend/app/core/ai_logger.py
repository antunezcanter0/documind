# app/core/ai_logger.py
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

class AILogger:
    """Logger especializado para operaciones de AI/ML"""
    
    def __init__(self, name: str = "ai_engineering"):
        self.logger = logging.getLogger(name)
        self.setup_logger()
    
    def setup_logger(self):
        """Configura el logger con formato estructurado"""
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # File handler para operaciones AI
            file_handler = logging.FileHandler('logs/ai_operations.log')
            file_handler.setLevel(logging.DEBUG)
            
            # Formato estructurado
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
            )
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.DEBUG)
    
    def log_model_inference(self, 
                          model_name: str, 
                          operation: str,
                          input_tokens: int = 0,
                          output_tokens: int = 0,
                          duration: float = 0.0,
                          metadata: Optional[Dict[str, Any]] = None):
        """Loggear inferencia de modelo"""
        log_entry = {
            "event_type": "model_inference",
            "model_name": model_name,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration * 1000,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.logger.info(f"MODEL_INFERENCE: {json.dumps(log_entry)}")
    
    def log_embedding_operation(self,
                              model_name: str,
                              text_length: int,
                              chunk_count: int,
                              duration: float,
                              metadata: Optional[Dict[str, Any]] = None):
        """Loggear operación de embeddings"""
        log_entry = {
            "event_type": "embedding_operation",
            "model_name": model_name,
            "text_length": text_length,
            "chunk_count": chunk_count,
            "duration_ms": duration * 1000,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.logger.info(f"EMBEDDING_OPERATION: {json.dumps(log_entry)}")
    
    def log_rag_operation(self,
                         query: str,
                         documents_found: int,
                         chunks_used: int,
                         duration: float,
                         has_context: bool,
                         metadata: Optional[Dict[str, Any]] = None):
        """Loggear operación RAG"""
        log_entry = {
            "event_type": "rag_operation",
            "query_length": len(query),
            "documents_found": documents_found,
            "chunks_used": chunks_used,
            "has_context": has_context,
            "duration_ms": duration * 1000,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.logger.info(f"RAG_OPERATION: {json.dumps(log_entry)}")
    
    def log_document_processing(self,
                               filename: str,
                               file_type: str,
                               file_size: int,
                               chunk_count: int,
                               duration: float,
                               success: bool,
                               error: Optional[str] = None):
        """Loggear procesamiento de documentos"""
        log_entry = {
            "event_type": "document_processing",
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "chunk_count": chunk_count,
            "duration_ms": duration * 1000,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error
        }
        status = "SUCCESS" if success else "ERROR"
        self.logger.info(f"DOCUMENT_PROCESSING_{status}: {json.dumps(log_entry)}")
    
    def log_api_request(self,
                       endpoint: str,
                       method: str,
                       duration: float,
                       status_code: int,
                       user_id: Optional[str] = None):
        """Loggear requests de API"""
        log_entry = {
            "event_type": "api_request",
            "endpoint": endpoint,
            "method": method,
            "duration_ms": duration * 1000,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id
        }
        self.logger.info(f"API_REQUEST: {json.dumps(log_entry)}")


# Logger global
ai_logger = AILogger()

# Decoradores para logging automático
def log_model_inference(model_name: str = None):
    """Decorator para loggear inferencias de modelos"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_msg = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                duration = time.time() - start_time
                # Intentar obtener nombre del modelo de kwargs o usar el proporcionado
                actual_model_name = model_name or kwargs.get('model', 'unknown')
                
                ai_logger.log_model_inference(
                    model_name=actual_model_name,
                    operation=func.__name__,
                    duration=duration,
                    metadata={"success": success, "error": error_msg}
                )
        return async_wrapper
    return decorator

def log_embedding_operation(model_name: str = None):
    """Decorator para loggear operaciones de embeddings"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_msg = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                duration = time.time() - start_time
                actual_model_name = model_name or kwargs.get('model', 'unknown')
                
                # Intentar obtener métricas de los argumentos
                texts = args[1] if len(args) > 1 and isinstance(args[1], list) else []
                text_length = sum(len(text) for text in texts)
                chunk_count = len(texts)
                
                ai_logger.log_embedding_operation(
                    model_name=actual_model_name,
                    text_length=text_length,
                    chunk_count=chunk_count,
                    duration=duration,
                    metadata={"success": success, "error": error_msg}
                )
        return async_wrapper
    return decorator

def log_performance(func):
    """Decorator para loggear performance de funciones"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            ai_logger.logger.info(f"PERFORMANCE: {func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            ai_logger.logger.error(f"PERFORMANCE: {func.__name__} failed in {duration:.3f}s: {e}")
            raise
    return async_wrapper
