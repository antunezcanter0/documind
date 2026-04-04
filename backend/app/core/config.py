from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "DocuMind"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "documind"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

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