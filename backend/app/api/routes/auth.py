from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new citizen and issues a JWT access token."""
    user = auth_service.register_citizen(db, req)
    token = auth_service.create_user_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        public_id=user.public_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department_id=user.department_id
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticates a citizen, officer, or admin and issues a JWT access token."""
    user = auth_service.authenticate_user(db, req)
    token = auth_service.create_user_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        public_id=user.public_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department_id=user.department_id
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return current_user


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logs out the user session."""
    return {"message": "Logged out successfully"}
