# app/core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_token, validate_token_payload, PermissionChecker
from app.core.ai_logger import ai_logger
from app.models.user import User

# Scheme para JWT
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Obtener usuario actual del token JWT"""
    
    try:
        # Verificar token
        payload = verify_token(credentials.credentials, "access")
        
        # Validar payload
        token_data = validate_token_payload(payload)
        
        # Obtener usuario de la base de datos
        stmt = select(User).where(User.username == token_data["username"])
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            ai_logger.logger.warning(f"User not found: {token_data['username']}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            ai_logger.logger.warning(f"Inactive user attempted access: {user.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Actualizar último login
        user.last_login = datetime.utcnow()
        user.login_count += 1
        await db.commit()
        
        ai_logger.logger.info(f"User authenticated successfully: {user.username}")
        return user
        
    except Exception as e:
        ai_logger.logger.error(f"Authentication failed: {str(e)}")
        raise

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Obtener usuario activo actual"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Obtener superusuario actual"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

def require_permission(resource: str, action: str):
    """Decorator para requerir permiso específico"""
    def permission_checker(current_user: User = Depends(get_current_active_user)):
        if not PermissionChecker.can_access_system(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for {resource}:{action}"
            )
        
        # Verificar permiso específico
        if resource == "documents":
            if action == "read" and not PermissionChecker.can_read_documents(current_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to read documents"
                )
            elif action == "write" and not PermissionChecker.can_write_documents(current_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to write documents"
                )
            elif action == "delete" and not PermissionChecker.can_delete_documents(current_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to delete documents"
                )
        
        elif resource == "users":
            if not PermissionChecker.can_manage_users(current_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to manage users"
                )
        
        elif resource == "system":
            if not PermissionChecker.can_access_system(current_user.role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to access system functions"
                )
        
        return current_user
    
    return permission_checker

def require_own_resource(resource_owner_id_param: str = "user_id"):
    """Decorator para requerir que el usuario sea dueño del recurso"""
    def owner_checker(
        current_user: User = Depends(get_current_active_user),
        **kwargs
    ):
        # Para superusuarios, permitir acceso a todo
        if current_user.is_superuser:
            return current_user
        
        # Verificar si el usuario es dueño del recurso
        resource_owner_id = kwargs.get(resource_owner_id_param)
        if resource_owner_id and str(resource_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only access your own resources"
            )
        
        return current_user
    
    return owner_checker

class OptionalAuth:
    """Clase para autenticación opcional (endpoints públicos)"""
    
    @staticmethod
    async def get_current_user_optional(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> User | None:
        """Obtener usuario actual si hay token, sino None"""
        if not credentials:
            return None
        
        try:
            payload = verify_token(credentials.credentials, "access")
            token_data = validate_token_payload(payload)
            
            stmt = select(User).where(User.username == token_data["username"])
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user and user.is_active:
                return user
            
        except Exception:
            pass
        
        return None

# Instancias para uso común
get_optional_current_user = OptionalAuth.get_current_user_optional

# Role-based access decorators
def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Requerir rol de administrador"""
    if current_user.role not in ["admin", "superuser"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def require_editor_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Requerir rol de editor o administrador"""
    if current_user.role not in ["editor", "admin", "superuser"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor or admin access required"
        )
    return current_user

def require_viewer_or_above(current_user: User = Depends(get_current_active_user)) -> User:
    """Requerir rol de viewer o superior"""
    if current_user.role not in ["viewer", "editor", "admin", "superuser"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer access or higher required"
        )
    return current_user
