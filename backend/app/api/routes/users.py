from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.security import get_password_hash
from app.core.exceptions import ConflictException, NotFoundException
from app.models.user import User, UserRole
from app.models.department import Department
from app.schemas.user import UserResponse, UserUpdate, UserCreateOfficer

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """Fetches profile of currently logged-in user."""
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_user_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates profile of currently logged-in user."""
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    if user_in.phone is not None:
        current_user.phone = user_in.phone

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("", response_model=List[UserResponse])
def list_users(
    role: Optional[UserRole] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Admin-only endpoint to list all system users."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/officer", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_officer(
    req: UserCreateOfficer,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Admin-only endpoint to provision a new Department Officer."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise ConflictException(f"User with email '{req.email}' already exists")

    dept = db.query(Department).filter(Department.id == req.department_id).first()
    if not dept:
        raise NotFoundException("Department not found")

    officer = User(
        full_name=req.full_name,
        email=req.email.lower(),
        phone=req.phone,
        password_hash=get_password_hash(req.password),
        role=UserRole.OFFICER,
        department_id=dept.id,
        is_active=True
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return officer
