from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import require_role
from app.core.exceptions import NotFoundException, ConflictException
from app.models.user import User, UserRole
from app.models.department import Department
from app.schemas.department import DepartmentResponse, DepartmentCreate, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentResponse])
def list_departments(db: Session = Depends(get_db)):
    """Lists all civic departments."""
    return db.query(Department).order_by(Department.name.asc()).all()


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(department_id: int, db: Session = Depends(get_db)):
    """Fetches details of a single department."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise NotFoundException("Department not found")
    return dept


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    dept_in: DepartmentCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Admin-only endpoint to register a new department."""
    existing = db.query(Department).filter(Department.code == dept_in.code.upper()).first()
    if existing:
        raise ConflictException(f"Department code '{dept_in.code}' already exists")

    dept = Department(
        code=dept_in.code.upper(),
        name=dept_in.name,
        description=dept_in.description,
        is_active=dept_in.is_active
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.put("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: int,
    dept_in: DepartmentUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Admin-only endpoint to update a department's details."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise NotFoundException("Department not found")

    if dept_in.name is not None:
        dept.name = dept_in.name
    if dept_in.description is not None:
        dept.description = dept_in.description
    if dept_in.is_active is not None:
        dept.is_active = dept_in.is_active

    db.commit()
    db.refresh(dept)
    return dept
