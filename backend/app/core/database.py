from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Usar conexión síncrona para evitar timeouts de asyncpg
database_url = settings.DATABASE_URL

engine = create_engine(
    database_url,
    echo=False,  # Reducir verbosidad
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    connect_args={
        "application_name": "documind_backend"
    }
)

SessionLocal = sessionmaker(
    engine,
    expire_on_commit=False
)

Base = declarative_base()

def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()