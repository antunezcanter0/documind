from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import health, documents, chat, metrics, cache, tasks, auth
from app.core.cache import cache_manager

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(metrics.router, prefix=settings.API_V1_STR)
app.include_router(cache.router, prefix=settings.API_V1_STR)
app.include_router(tasks.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to DocuMind API", "version": "1.0.0"}

@app.on_event("startup")
async def startup_event():
    """Conectar a Redis en startup"""
    try:
        await cache_manager.connect()
        print(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    except Exception as e:
        print(f"⚠️  Failed to connect to Redis: {e}")
        print("🔄 Continuing without cache...")

@app.on_event("shutdown")
async def shutdown_event():
    """Desconectar de Redis en shutdown"""
    try:
        await cache_manager.disconnect()
        print("✅ Disconnected from Redis")
    except Exception as e:
        print(f"⚠️  Error disconnecting from Redis: {e}")