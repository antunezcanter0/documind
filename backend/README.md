# 📚 DocuMind - Sistema RAG con IA Local

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-red.svg)](https://redis.io/)
[![Ollama](https://img.shields.io/badge/Ollama-Local-orange.svg)](https://ollama.ai/)

**DocuMind** es un sistema de **Retrieval-Augmented Generation (RAG)** que permite hacer preguntas a documentos usando inteligencia artificial local. Procesa múltiples formatos de documentos, los indexa con embeddings y permite consultas semánticas con respuestas generadas por LLM.

## 🎯 **Características Principales**

### ✅ **Funcionalidades Actuales**
- 📄 **Procesamiento Multi-formato**: PDF, DOCX, TXT, MD, HTML
- 🔍 **Búsqueda Semántica**: Búsqueda vectorial con pgvector
- 🤖 **IA Local**: LLM y embeddings con Ollama
- ⚡ **Caché Inteligente**: Redis para optimizar rendimiento
- 🏥 **Health Checks**: Monitoreo de todos los componentes
- 🚀 **API RESTful**: Endpoints completos para integración

### 🔄 **Flujo RAG**
```
Documento → Procesamiento → Embeddings → Base de Datos Vectorial
                                                ↓
Pregunta → Embeddings → Búsqueda Semántica → Contexto → LLM → Respuesta
```

## 🏗️ **Arquitectura del Sistema**

### **Componentes Principales**

#### **🔧 Backend (FastAPI)**
- **Framework**: FastAPI 0.104.1 con Uvicorn
- **Base de Datos**: PostgreSQL + pgvector
- **Caché**: Redis 5.0.0
- **IA**: Ollama (llama3.2:3b + nomic-embed-text)

#### **📊 Estructura del Proyecto**
```
backend/
├── app/
│   ├── api/                    # Endpoints REST
│   │   ├── health.py          # Health checks del sistema
│   │   ├── documents.py       # Gestión de documentos
│   │   ├── chat.py            # Chat RAG
│   │   └── cache.py           # Gestión de caché
│   ├── core/                   # Componentes centrales
│   │   ├── config.py          # Configuración Pydantic
│   │   ├── database.py        # Conexión a PostgreSQL
│   │   └── cache.py           # Gestión Redis
│   ├── models/                 # Modelos de datos
│   │   └── document.py        # Modelo Document
│   ├── services/               # Lógica de negocio
│   │   ├── rag_service.py     # Core RAG
│   │   ├── embedding_service.py # Embeddings
│   │   ├── llm_service.py     # LLM interaction
│   │   └── document_processor.py # Procesamiento docs
│   └── main.py                # Aplicación FastAPI
├── requirements.txt            # Dependencias Python
└── .env                       # Variables de entorno
```

## 🚀 **Instalación y Configuración**

### **Prerrequisitos**
- Python 3.12+
- PostgreSQL 15+ con pgvector
- Redis 7+
- Ollama (para IA local)

### **1. Clonar y Configurar Entorno**
```bash
# Clonar repositorio
git clone <repository-url>
cd documind/backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### **2. Configurar Base de Datos PostgreSQL**
```sql
-- Crear base de datos con pgvector
CREATE DATABASE documind;

-- Crear usuario
CREATE USER documind_user WITH PASSWORD 'documind_secure_password_2024';

-- Dar permisos
GRANT ALL PRIVILEGES ON DATABASE documind TO documind_user;

-- Conectar a la base y habilitar pgvector
\c documind
CREATE EXTENSION IF NOT EXISTS vector;
```

### **3. Configurar Ollama**
```bash
# Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Descargar modelos
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# Iniciar Ollama
ollama serve
```

### **4. Configurar Redis**
```bash
# Instalar Redis (Ubuntu/Debian)
sudo apt update
sudo apt install redis-server

# Iniciar Redis
sudo systemctl start redis
sudo systemctl enable redis
```

### **5. Configurar Variables de Entorno**
```bash
# Copiar archivo de configuración
cp .env.example .env

# Editar .env con tus configuraciones
nano .env
```

#### **Configuración .env**
```env
# =================================
# 🗄️ BASE DE DATOS POSTGRESQL
# =================================
POSTGRES_SERVER=127.0.0.1
POSTGRES_USER=documind_user
POSTGRES_PASSWORD=documind_secure_password_2024
POSTGRES_DB=documind
POSTGRES_PORT=5432

# =================================
# 🔄 REDIS CACHE Y COLAS
# =================================
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# =================================
# 🤖 SERVICIOS DE IA (OLLAMA)
# =================================
OPENAI_API_KEY=not-needed
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2:3b
EMBEDDING_MODEL=nomic-embed-text

# =================================
# ⚙️ CONFIGURACIÓN API
# =================================
API_V1_STR=/api/v1
PROJECT_NAME=DocuMind

# =================================
# 🐛 DESARROLLO (opcional)
# =================================
DEBUG=true
LOG_LEVEL=DEBUG
RELOAD=true
```

## 🚀 **Ejecución**

### **Iniciar el Servidor**
```bash
# Desde el directorio backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **Verificar Instalación**
```bash
# Health check completo
curl http://localhost:8000/api/v1/health/detailed

# Health check simple
curl http://localhost:8000/api/v1/health/ready

# Documentación API
open http://localhost:8000/docs
```

## 📖 **Uso de la API**

### **Endpoints Principales**

#### **📄 Gestión de Documentos**
```bash
# Subir documento
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@documento.pdf"

# Listar documentos
curl "http://localhost:8000/api/v1/documents/list?skip=0&limit=10"
```

#### **💬 Chat RAG**
```bash
# Hacer pregunta a documentos
curl -X POST "http://localhost:8000/api/v1/chat/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cuál es el tema principal del documento?"}'

# Búsqueda semántica
curl -X POST "http://localhost:8000/api/v1/chat/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "top_k": 5}'
```

#### **🗄️ Gestión de Caché**
```bash
# Estadísticas de caché
curl "http://localhost:8000/api/v1/cache/stats"

# Limpiar caché de embeddings
curl -X DELETE "http://localhost:8000/api/v1/cache/clear/embeddings"

# Health check de Redis
curl "http://localhost:8000/api/v1/cache/health"
```

#### **🏥 Health Checks**
```bash
# Health check completo
curl "http://localhost:8000/api/v1/health/detailed"

# Health check de componentes específicos
curl "http://localhost:8000/api/v1/health/database"
curl "http://localhost:8000/api/v1/health/ollama"
curl "http://localhost:8000/api/v1/health/redis"
```

## 🔧 **Configuración Avanzada**

### **Modelos de IA Soportados**
- **LLM**: llama3.2:3b, llama3.1:8b, qwen3:8b, mistral:7b
- **Embeddings**: nomic-embed-text, all-minilm:22m, e5-small

### **Formatos de Documentos Soportados**
- 📄 **PDF**: Extrae texto y metadatos
- 📝 **DOCX**: Documentos Word
- 📄 **TXT**: Texto plano
- 📝 **Markdown**: Formato MD
- 🌐 **HTML**: Páginas web

### **Configuración de Caché**
```python
# TTL por defecto (configurable en código)
EMBEDDING_CACHE_TTL = 3600  # 1 hora
RAG_CACHE_TTL = 300         # 5 minutos  
LLM_CACHE_TTL = 600         # 10 minutos
```

## 📊 **Monitorización y Salud**

### **Componentes Monitoreados**
- ✅ **PostgreSQL**: Conexión y consultas
- ✅ **Redis**: Conexión y estadísticas
- ✅ **Ollama**: LLM y embeddings
- ✅ **Sistema**: Memoria y CPU

### **Health Checks Disponibles**
- `/api/v1/health` - Health básico
- `/api/v1/health/detailed` - Health completo
- `/api/v1/health/ready` - Readiness probe
- `/api/v1/health/live` - Liveness probe

## 🛠️ **Dependencias**

### **Core Framework**
- `fastapi==0.104.1` - Framework web
- `uvicorn[standard]==0.24.0` - Servidor ASGI
- `pydantic==2.5.0` - Validación de datos
- `pydantic-settings==2.1.0` - Configuración

### **Base de Datos**
- `sqlalchemy==2.0.23` - ORM
- `asyncpg==0.29.0` - Driver async PostgreSQL
- `pgvector==0.2.4` - Extension vectorial

### **IA y Procesamiento**
- `openai==2.33.0` - Cliente Ollama (compatible)
- `tiktoken==0.12.0` - Token counting
- `pypdf2==3.0.1` - Procesamiento PDF
- `python-docx==1.2.0` - Procesamiento DOCX
- `beautifulsoup4==4.14.3` - Procesamiento HTML
- `markdown==3.10.2` - Procesamiento MD
- `python-magic==0.4.27` - Detección de tipos

### **Caché y Utilidades**
- `redis==5.0.0` - Cliente Redis
- `psutil==5.9.0` - Monitorización sistema
- `python-dotenv==1.0.0` - Variables de entorno

## 🚨 **Solución de Problemas**

### **Errores Comunes**

#### **1. Error de conexión PostgreSQL**
```bash
# Verificar que PostgreSQL está corriendo
sudo systemctl status postgresql

# Verificar pgvector
psql -d documind -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

#### **2. Error de conexión Redis**
```bash
# Verificar Redis
redis-cli ping

# Verificar configuración
redis-cli info server
```

#### **3. Error de conexión Ollama**
```bash
# Verificar Ollama
ollama list
curl http://localhost:11434/api/tags

# Reiniciar Ollama
pkill ollama && ollama serve
```

#### **4. Error de dependencias Python**
```bash
# Reinstalar dependencias
pip uninstall -r requirements.txt -y
pip install -r requirements.txt

# Verificar versión Python
python --version  # Debe ser 3.12+
```

### **Logs y Debug**
```bash
# Habilitar debug en .env
DEBUG=true
LOG_LEVEL=DEBUG

# Ver logs del servidor
uvicorn app.main:app --reload --log-level debug
```

## 🔄 **Roadmap Futuro**

### **Próximas Características**
- 🔐 **Autenticación JWT**: Sistema de usuarios
- 📊 **Analytics**: Métricas de uso
- 🧪 **Testing**: Suite de pruebas completo
- 🐳 **Docker**: Contenerización
- 📈 **Monitoring**: Prometheus + Grafana
- 🔄 **Streaming**: Respuestas en streaming
- 📚 **Multi-idioma**: Soporte internacional

### **Mejoras de Rendimiento**
- ⚡ **Batch Processing**: Procesamiento por lotes
- 🔄 **Async Tasks**: Colas con Celery
- 📊 **Vector Index**: Índices optimizados
- 🗄️ **Database Pooling**: Pool de conexiones

## 🤝 **Contribución**

### **Guía de Contribución**
1. Fork del proyecto
2. Crear feature branch
3. Hacer cambios con tests
4. Pull request con descripción

### **Estándares de Código**
- Python 3.12+ con type hints
- Formato con black
- Linting con flake8
- Tests con pytest

## 📄 **Licencia**

Este proyecto está bajo licencia MIT. Ver archivo [LICENSE](LICENSE) para más detalles.

## 📞 **Soporte**

### **Documentación**
- 📖 [API Docs](http://localhost:8000/docs)
- 🎯 [OpenAPI Spec](http://localhost:8000/openapi.json)

### **Issues y Soporte**
- 🐛 Reportar bugs en GitHub Issues
- 💡 Feature requests en Discussions
- 📧 Contacto directo para soporte empresarial

---

**🚀 DocuMind - IA Local para Documentos**

Transforma tus documentos en conocimiento conversacional con IA local y privada.
