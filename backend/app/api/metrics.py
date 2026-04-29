# app/api/metrics.py
from fastapi import APIRouter, HTTPException
from app.core.metrics import ai_metrics
from app.core.ai_logger import ai_logger
from typing import Dict, Any

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/")
async def get_all_metrics() -> Dict[str, Any]:
    """Obtener todas las métricas del sistema"""
    try:
        return ai_metrics.get_all_metrics()
    except Exception as e:
        ai_logger.logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving metrics")

@router.get("/models/{model_name}")
async def get_model_metrics(model_name: str) -> Dict[str, Any]:
    """Obtener métricas de un modelo específico"""
    try:
        metrics = ai_metrics.get_model_metrics(model_name)
        if not metrics:
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        ai_logger.logger.error(f"Error getting model metrics: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving model metrics")

@router.get("/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """Obtener resumen de métricas clave"""
    try:
        all_metrics = ai_metrics.get_all_metrics()
        
        summary = {
            "total_requests": all_metrics["counters"].get("rag_operations_total", 0),
            "total_documents": all_metrics["counters"].get("document_processing_total", 0),
            "total_inferences": all_metrics["counters"].get("model_inferences_total", 0),
            "avg_rag_duration": all_metrics["timers"].get("rag_operation_duration", {}).get("avg", 0),
            "avg_inference_duration": all_metrics["timers"].get("model_inference_duration", {}).get("avg", 0),
            "model_performance": {},
            "recent_activity": {
                "timestamp": all_metrics["timestamp"],
                "active_models": len(all_metrics["model_metrics"])
            }
        }
        
        # Agregar performance de modelos
        for model_name, model_data in all_metrics["model_metrics"].items():
            summary["model_performance"][model_name] = {
                "total_inferences": model_data.get("total_inferences", 0),
                "success_rate": model_data.get("success_rate", 0),
                "avg_duration": model_data.get("avg_duration", 0),
                "last_inference": model_data.get("last_inference")
            }
        
        return summary
    except Exception as e:
        ai_logger.logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving metrics summary")

@router.post("/reset")
async def reset_metrics() -> Dict[str, str]:
    """Resetear todas las métricas (solo para desarrollo)"""
    try:
        ai_metrics.reset()
        ai_logger.logger.info("All metrics reset")
        return {"message": "Metrics reset successfully"}
    except Exception as e:
        ai_logger.logger.error(f"Error resetting metrics: {e}")
        raise HTTPException(status_code=500, detail="Error resetting metrics")
