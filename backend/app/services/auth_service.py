from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, LoginRequest
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.exceptions import BadRequestException, ConflictException, UnauthorizedException


class AuthService:
    def register_citizen(self, db: Session, req: RegisterRequest) -> User:
        # Check if email already registered
        existing = db.query(User).filter(User.email == req.email.lower()).first()
        if existing:
            raise ConflictException(f"User with email '{req.email}' already exists")

        user = User(
            full_name=req.full_name,
            email=req.email.lower(),
            phone=req.phone,
            password_hash=get_password_hash(req.password),
            role=UserRole.CITIZEN,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def authenticate_user(self, db: Session, req: LoginRequest) -> User:
        user = db.query(User).filter(User.email == req.email.lower()).first()
        if not user:
            raise UnauthorizedException("Invalid email or password")

        if not verify_password(req.password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedException("Account is deactivated")

        return user

    def create_user_token(self, user: User) -> str:
        return create_access_token(subject=user.id, role=user.role.value)


auth_service = AuthService()
