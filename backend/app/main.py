from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import health#, documents, chat

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
# app.include_router(documents.router, prefix=settings.API_V1_STR)
# app.include_router(chat.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to DocuMind API", "version": "1.0.0"}