# app/api/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, verify_token,
    get_password_hash, verify_password, create_token_response,
    get_token_expiration_time
)
from app.core.auth import get_current_user, get_current_active_user, require_admin
from app.core.ai_logger import ai_logger
from app.core.metrics import ai_metrics
from app.models.user import User, RefreshToken
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "user"

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str]
    login_count: int

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_token_expires_in: int

class TokenRefresh(BaseModel):
    refresh_token: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Registrar nuevo usuario"""
    
    # Verificar si el usuario ya existe
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Verificar si el email ya existe
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validar rol
    valid_roles = ["user", "viewer", "editor", "admin"]
    if user_data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {valid_roles}"
        )
    
    # Crear usuario
    hashed_password = get_password_hash(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    ai_logger.logger.info(f"User registered: {user.username} with role {user.role}")
    ai_metrics.increment_counter("user_registrations")
    
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
        login_count=user.login_count
    )

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login de usuario"""
    
    # Verificar usuario
    stmt = select(User).where(User.username == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        ai_logger.logger.warning(f"Login failed for username: {form_data.username}")
        ai_metrics.increment_counter("login_attempts_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        ai_logger.logger.warning(f"Login attempt for inactive user: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crear tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": str(user.id)},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": str(user.id)},
        expires_delta=refresh_token_expires
    )
    
    # Guardar refresh token en BD
    refresh_token_obj = RefreshToken(
        user_id=user.id,
        token_hash=get_password_hash(refresh_token),
        expires_at=get_token_expiration_time(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60)
    )
    db.add(refresh_token_obj)
    await db.commit()
    
    ai_logger.logger.info(f"User logged in: {user.username}")
    ai_metrics.increment_counter("login_attempts_success")
    
    return create_token_response(access_token, refresh_token)

@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """Refrescar access token usando refresh token"""
    
    try:
        # Verificar refresh token
        payload = verify_token(token_data.refresh_token, "refresh")
        username = payload.get("sub")
        user_id = payload.get("user_id")
        
        if not username or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Verificar que el refresh token exista en BD
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        )
        result = await db.execute(stmt)
        refresh_tokens = result.scalars().all()
        
        # Verificar si alguno de los tokens coincide
        valid_token = None
        for rt in refresh_tokens:
            if verify_password(token_data.refresh_token, rt.token_hash):
                valid_token = rt
                break
        
        if not valid_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Obtener usuario
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Crear nuevo access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role, "user_id": str(user.id)},
            expires_delta=access_token_expires
        )
        
        ai_logger.logger.info(f"Token refreshed for user: {user.username}")
        ai_metrics.increment_counter("token_refreshes")
        
        return create_token_response(access_token)
        
    except HTTPException:
        raise
    except Exception as e:
        ai_logger.logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout - revocar refresh tokens del usuario"""
    
    # Revocar todos los refresh tokens del usuario
    stmt = select(RefreshToken).where(RefreshToken.user_id == current_user.id)
    result = await db.execute(stmt)
    refresh_tokens = result.scalars().all()
    
    for rt in refresh_tokens:
        rt.is_revoked = True
    
    await db.commit()
    
    ai_logger.logger.info(f"User logged out: {current_user.username}")
    ai_metrics.increment_counter("user_logouts")
    
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Obtener información del usuario actual"""
    
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
        login_count=current_user.login_count
    )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Actualizar información del usuario actual"""
    
    # Actualizar campos permitidos
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    if user_update.email is not None:
        # Verificar que el email no esté en uso por otro usuario
        stmt = select(User).where(
            User.email == user_update.email,
            User.id != current_user.id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = user_update.email
    
    if user_update.bio is not None:
        current_user.bio = user_update.bio
    
    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url
    
    await db.commit()
    await db.refresh(current_user)
    
    ai_logger.logger.info(f"User updated profile: {current_user.username}")
    ai_metrics.increment_counter("user_profile_updates")
    
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
        login_count=current_user.login_count
    )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Cambiar contraseña del usuario actual"""
    
    # Verificar contraseña actual
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Actualizar contraseña
    current_user.hashed_password = get_password_hash(password_data.new_password)
    
    # Revocar todos los refresh tokens (forzar re-login)
    stmt = select(RefreshToken).where(RefreshToken.user_id == current_user.id)
    result = await db.execute(stmt)
    refresh_tokens = result.scalars().all()
    
    for rt in refresh_tokens:
        rt.is_revoked = True
    
    await db.commit()
    
    ai_logger.logger.info(f"Password changed for user: {current_user.username}")
    ai_metrics.increment_counter("password_changes")
    
    return {"message": "Password changed successfully"}

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Listar usuarios (solo admin)"""
    
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    return [
        UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None,
            login_count=user.login_count
        )
        for user in users
    ]

@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Desactivar usuario (solo admin)"""
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate superuser"
        )
    
    user.is_active = False
    
    # Revocar todos los refresh tokens
    stmt = select(RefreshToken).where(RefreshToken.user_id == user.id)
    result = await db.execute(stmt)
    refresh_tokens = result.scalars().all()
    
    for rt in refresh_tokens:
        rt.is_revoked = True
    
    await db.commit()
    
    ai_logger.logger.info(f"User deactivated: {user.username} by {current_user.username}")
    ai_metrics.increment_counter("user_deactivations")
    
    return {"message": f"User {user.username} deactivated successfully"}
