from typing import Generator, List, Optional
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not auth or not auth.credentials:
        raise UnauthorizedException("Authentication token required")
    
    payload = decode_access_token(auth.credentials)
    if not payload:
        raise UnauthorizedException("Invalid or expired access token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Malformed token payload")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise UnauthorizedException("User associated with token no longer exists")
    
    if not user.is_active:
        raise ForbiddenException("User account is deactivated")
        
    return user


def get_optional_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not auth or not auth.credentials:
        return None
    
    payload = decode_access_token(auth.credentials)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None


def require_role(*allowed_roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(f"Access denied: required role in {[r.value for r in allowed_roles]}")
        return current_user
    return role_checker
