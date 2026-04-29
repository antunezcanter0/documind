# app/core/metrics.py
import time
import threading
from collections import defaultdict, deque
from typing import Dict, List, Any
from datetime import datetime, timedelta

class AIMetrics:
    """Sistema de métricas para operaciones de AI/ML"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.lock = threading.Lock()
        
        # Contadores
        self.counters = defaultdict(int)
        
        # Histograms para distribuciones
        self.histograms = defaultdict(lambda: deque(maxlen=max_history))
        
        # Gauges para valores actuales
        self.gauges = defaultdict(float)
        
        # Timers para duraciones
        self.timers = defaultdict(lambda: deque(maxlen=max_history))
        
        # Métricas específicas de AI
        self.model_metrics = defaultdict(dict)
        self.document_metrics = defaultdict(dict)
    
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Incrementar un contador"""
        key = self._make_key(name, labels)
        with self.lock:
            self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Establecer un gauge"""
        key = self._make_key(name, labels)
        with self.lock:
            self.gauges[key] = value
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Registrar un valor en histograma"""
        key = self._make_key(name, labels)
        with self.lock:
            self.histograms[key].append(value)
    
    def record_timer(self, name: str, duration: float, labels: Dict[str, str] = None):
        """Registrar una duración"""
        key = self._make_key(name, labels)
        with self.lock:
            self.timers[key].append(duration)
            self.histograms[f"{key}_duration"].append(duration)
    
    def record_model_inference(self, 
                             model_name: str,
                             operation: str,
                             input_tokens: int,
                             output_tokens: int,
                             duration: float,
                             success: bool = True):
        """Registrar métricas de inferencia de modelo"""
        labels = {
            "model": model_name,
            "operation": operation,
            "success": str(success)
        }
        
        # Contadores
        self.increment_counter("model_inferences_total", 1, labels)
        if not success:
            self.increment_counter("model_inferences_failed", 1, labels)
        
        # Tokens
        self.record_histogram("model_input_tokens", input_tokens, labels)
        self.record_histogram("model_output_tokens", output_tokens, labels)
        
        # Performance
        self.record_timer("model_inference_duration", duration, labels)
        
        # Métricas específicas del modelo
        with self.lock:
            if model_name not in self.model_metrics:
                self.model_metrics[model_name] = {
                    "total_inferences": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "avg_duration": 0.0,
                    "success_rate": 1.0,
                    "last_inference": None
                }
            
            metrics = self.model_metrics[model_name]
            metrics["total_inferences"] += 1
            metrics["total_input_tokens"] += input_tokens
            metrics["total_output_tokens"] += output_tokens
            metrics["last_inference"] = datetime.utcnow()
            
            # Actualizar promedio móvil
            alpha = 0.1  # Factor de suavizado
            metrics["avg_duration"] = (alpha * duration + 
                                     (1 - alpha) * metrics["avg_duration"])
            
            # Actualizar success rate
            if success:
                metrics["success_rate"] = (0.9 * metrics["success_rate"] + 0.1)
            else:
                metrics["success_rate"] = (0.9 * metrics["success_rate"])
    
    def record_embedding_operation(self,
                                 model_name: str,
                                 text_length: int,
                                 chunk_count: int,
                                 duration: float,
                                 success: bool = True):
        """Registrar métricas de operación de embeddings"""
        labels = {
            "model": model_name,
            "success": str(success)
        }
        
        # Contadores
        self.increment_counter("embedding_operations_total", 1, labels)
        if not success:
            self.increment_counter("embedding_operations_failed", 1, labels)
        
        # Métricas de operación
        self.record_histogram("embedding_text_length", text_length, labels)
        self.record_histogram("embedding_chunk_count", chunk_count, labels)
        self.record_timer("embedding_operation_duration", duration, labels)
    
    def record_rag_operation(self,
                           query_length: int,
                           documents_found: int,
                           chunks_used: int,
                           duration: float,
                           has_context: bool):
        """Registrar métricas de operación RAG"""
        labels = {
            "has_context": str(has_context)
        }
        
        # Contadores
        self.increment_counter("rag_operations_total", 1, labels)
        
        # Métricas de operación
        self.record_histogram("rag_query_length", query_length)
        self.record_histogram("rag_documents_found", documents_found)
        self.record_histogram("rag_chunks_used", chunks_used)
        self.record_timer("rag_operation_duration", duration)
        
        # Gauges
        self.set_gauge("rag_current_avg_chunks_per_query", chunks_used)
    
    def record_document_processing(self,
                                 file_type: str,
                                 file_size: int,
                                 chunk_count: int,
                                 duration: float,
                                 success: bool):
        """Registrar métricas de procesamiento de documentos"""
        labels = {
            "file_type": file_type,
            "success": str(success)
        }
        
        # Contadores
        self.increment_counter("document_processing_total", 1, labels)
        if not success:
            self.increment_counter("document_processing_failed", 1, labels)
        
        # Métricas de operación
        self.record_histogram("document_file_size", file_size, labels)
        self.record_histogram("document_chunk_count", chunk_count, labels)
        self.record_timer("document_processing_duration", duration, labels)
    
    def get_model_metrics(self, model_name: str) -> Dict[str, Any]:
        """Obtener métricas de un modelo específico"""
        with self.lock:
            return self.model_metrics.get(model_name, {}).copy()
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Obtener todas las métricas"""
        with self.lock:
            # Calcular estadísticas de histograms
            histogram_stats = {}
            for key, values in self.histograms.items():
                if values:
                    histogram_stats[key] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "recent_avg": sum(list(values)[-10:]) / min(len(values), 10)
                    }
            
            # Calcular estadísticas de timers
            timer_stats = {}
            for key, values in self.timers.items():
                if values:
                    timer_stats[key] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
            
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": histogram_stats,
                "timers": timer_stats,
                "model_metrics": dict(self.model_metrics),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Crear clave con labels"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calcular percentil"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def reset(self):
        """Resetear todas las métricas"""
        with self.lock:
            self.counters.clear()
            self.histograms.clear()
            self.gauges.clear()
            self.timers.clear()
            self.model_metrics.clear()
            self.document_metrics.clear()


# Métricas global
ai_metrics = AIMetrics()

# Decoradores para métricas automáticas
def track_model_metrics(model_name: str = None):
    """Decorator para trackear métricas de modelo automáticamente"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                actual_model_name = model_name or kwargs.get('model', 'unknown')
                
                # Intentar extraer métricas de los argumentos
                input_tokens = kwargs.get('input_tokens', 0)
                output_tokens = kwargs.get('output_tokens', 0)
                
                ai_metrics.record_model_inference(
                    model_name=actual_model_name,
                    operation=func.__name__,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration=duration,
                    success=success
                )
        return wrapper
    return decorator

def track_performance(name: str = None):
    """Decorator para trackear performance automáticamente"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                ai_metrics.record_timer(name or f"{func.__name__}_duration", duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                ai_metrics.record_timer(f"{name or func.__name__}_duration_failed", duration)
                raise
        return wrapper
    return decorator
