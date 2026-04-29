# app/core/security.py
from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.ai_logger import ai_logger
from app.core.metrics import ai_metrics

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Role-based access control
ROLES = {
    "superuser": ["*"],  # Full access
    "admin": ["read", "write", "delete", "manage_users", "manage_system"],
    "editor": ["read", "write", "delete"],
    "viewer": ["read"],
    "user": ["read_own", "write_own"]
}

# Resource permissions
PERMISSIONS = {
    "documents": {
        "read": "documents:read",
        "write": "documents:write", 
        "delete": "documents:delete",
        "read_own": "documents:read_own",
        "write_own": "documents:write_own"
    },
    "chat": {
        "read": "chat:read",
        "write": "chat:write"
    },
    "users": {
        "read": "users:read",
        "write": "users:write",
        "delete": "users:delete"
    },
    "system": {
        "read": "system:read",
        "manage": "system:manage"
    }
}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    ai_logger.logger.info(f"Access token created for user: {data.get('sub')}")
    ai_metrics.increment_counter("access_tokens_created")
    
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear JWT refresh token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    ai_logger.logger.info(f"Refresh token created for user: {data.get('sub')}")
    ai_metrics.increment_counter("refresh_tokens_created")
    
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> dict:
    """Verificar JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Verificar tipo de token
        if payload.get("type") != token_type:
            raise JWTError("Invalid token type")
        
        username: str = payload.get("sub")
        if username is None:
            raise JWTError("Invalid token payload")
        
        # Verificar expiración
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp) < datetime.utcnow():
            raise JWTError("Token expired")
        
        return payload
        
    except JWTError as e:
        ai_logger.logger.warning(f"Token verification failed: {str(e)}")
        ai_metrics.increment_counter("token_verification_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_password_hash(password: str) -> str:
    """Generar hash de contraseña"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña"""
    result = pwd_context.verify(plain_password, hashed_password)
    if result:
        ai_metrics.increment_counter("password_verification_success")
    else:
        ai_metrics.increment_counter("password_verification_failed")
        ai_logger.logger.warning("Password verification failed")
    return result

def has_permission(user_role: str, required_permission: str) -> bool:
    """Verificar si un rol tiene un permiso específico"""
    if user_role == "superuser":
        return True
    
    role_permissions = ROLES.get(user_role, [])
    return "*" in role_permissions or required_permission in role_permissions

def check_permission(user_role: str, resource: str, action: str) -> bool:
    """Verificar permiso específico de recurso y acción"""
    if user_role == "superuser":
        return True
    
    # Construir permiso requerido
    permission = PERMISSIONS.get(resource, {}).get(action)
    if not permission:
        return False
    
    return has_permission(user_role, permission)

def require_permission(resource: str, action: str):
    """Decorator para requerir permiso específico"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Aquí se debería obtener el rol del usuario actual
            # Por ahora, implementación básica
            return func(*args, **kwargs)
        return wrapper
    return decorator

class PermissionChecker:
    """Clase para verificar permisos de usuario"""
    
    @staticmethod
    def can_read_documents(user_role: str, user_id: str = None, resource_owner_id: str = None) -> bool:
        """Verificar si puede leer documentos"""
        if check_permission(user_role, "documents", "read"):
            return True
        if check_permission(user_role, "documents", "read_own") and user_id == resource_owner_id:
            return True
        return False
    
    @staticmethod
    def can_write_documents(user_role: str, user_id: str = None, resource_owner_id: str = None) -> bool:
        """Verificar si puede escribir documentos"""
        if check_permission(user_role, "documents", "write"):
            return True
        if check_permission(user_role, "documents", "write_own") and user_id == resource_owner_id:
            return True
        return False
    
    @staticmethod
    def can_delete_documents(user_role: str, user_id: str = None, resource_owner_id: str = None) -> bool:
        """Verificar si puede eliminar documentos"""
        if check_permission(user_role, "documents", "delete"):
            return True
        return False
    
    @staticmethod
    def can_manage_users(user_role: str) -> bool:
        """Verificar si puede gestionar usuarios"""
        return check_permission(user_role, "users", "write")
    
    @staticmethod
    def can_access_system(user_role: str) -> bool:
        """Verificar si puede acceder a funciones del sistema"""
        return check_permission(user_role, "system", "read")

def get_user_permissions(user_role: str) -> list:
    """Obtener lista de permisos para un rol"""
    if user_role == "superuser":
        return ["*"]
    
    return ROLES.get(user_role, [])

def validate_token_payload(payload: dict) -> dict:
    """Validar y limpiar payload de token"""
    cleaned_payload = {}
    
    # Campos obligatorios
    if "sub" not in payload:
        raise JWTError("Missing subject in token")
    
    cleaned_payload["username"] = payload["sub"]
    cleaned_payload["role"] = payload.get("role", "user")
    cleaned_payload["user_id"] = payload.get("user_id")
    cleaned_payload["is_superuser"] = payload.get("is_superuser", False)
    
    return cleaned_payload

def create_token_response(access_token: str, refresh_token: str = None) -> dict:
    """Crear respuesta de autenticación estandarizada"""
    response = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
    
    if refresh_token:
        response["refresh_token"] = refresh_token
        response["refresh_token_expires_in"] = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    
    return response

def is_token_expired(payload: dict) -> bool:
    """Verificar si el token está expirado"""
    exp = payload.get("exp")
    if not exp:
        return True
    
    return datetime.fromtimestamp(exp) < datetime.utcnow()

def get_token_expiration_time(minutes: int = None) -> datetime:
    """Obtener tiempo de expiración del token"""
    minutes = minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    return datetime.utcnow() + timedelta(minutes=minutes)
