from typing import List, Dict
from pydantic import BaseModel


class CategoryStatItem(BaseModel):
    category: str
    count: int


class DepartmentStatItem(BaseModel):
    department_id: int
    department_name: str
    total: int
    pending: int
    in_progress: int
    resolved: int


class PriorityStatItem(BaseModel):
    priority: str
    count: int


class StatusStatItem(BaseModel):
    status: str
    count: int


class AdminDashboardStats(BaseModel):
    total_complaints: int
    submitted: int
    under_review: int
    assigned: int
    in_progress: int
    resolved: int
    rejected: int
    reopened: int
    overdue: int
    emergency_critical: int
    categories: List[CategoryStatItem]
    departments: List[DepartmentStatItem]
    priorities: List[PriorityStatItem]
    recent_activity: List[Dict] = []


class CitizenDashboardStats(BaseModel):
    total_submitted: int
    pending_review: int
    in_progress: int
    resolved: int
    recent_complaints: List[Dict] = []
