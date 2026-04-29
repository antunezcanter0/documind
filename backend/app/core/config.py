from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "DocuMind"

    # Database
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "documind"
    POSTGRES_PORT: str = "5434"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None

    @property
    def REDIS_CONNECTION_STRING(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Cache TTL (seconds)
    EMBEDDING_CACHE_TTL: int = 3600  # 1 hour
    RAG_CACHE_TTL: int = 300         # 5 minutes
    LLM_CACHE_TTL: int = 600         # 10 minutes

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CONFIGURACIÓN PARA OLLAMA (LOCAL) ---
    OPENAI_API_KEY: Optional[str] = "not-needed"  # Ollama no necesita clave
    # La URL base para la API local de Ollama
    OPENAI_BASE_URL: str = "http://localhost:11434/v1"
    # El modelo que descargaste (ej: llama3.2:3b, qwen3:8b, etc.)
    LLM_MODEL: str = "llama3.2:3b"
    # El modelo para embeddings (usaremos uno compatible)
    EMBEDDING_MODEL: str = "nomic-embed-text"  # Modelo popular para embeddings local

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()