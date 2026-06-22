from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# Auth
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    stack: str = "fullstack"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    stack: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# Project
class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


# Sprint
class SprintCreate(BaseModel):
    name: str
    project_id: int
    start_date: datetime
    end_date: datetime


class SprintOut(BaseModel):
    id: int
    name: str
    project_id: int
    start_date: datetime
    end_date: datetime

    class Config:
        from_attributes = True


# Task
class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    type: str = "backend"
    status: str = "todo"
    estimate_hours: float = 2.0
    project_id: int
    sprint_id: Optional[int] = None
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    estimate_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    sprint_id: Optional[int] = None
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    priority: str
    type: str
    status: str
    estimate_hours: float
    actual_hours: Optional[float]
    project_id: int
    sprint_id: Optional[int]
    assignee_id: Optional[int]
    reporter_id: Optional[int]
    ai_generated: bool
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    due_date: Optional[datetime]

    class Config:
        from_attributes = True

# ML
class EstimateRequest(BaseModel):
    type: str
    priority: str
    assignee_id: Optional[int] = None
    title: str = ""


class EstimateResponse(BaseModel):
    predicted_hours: float
    confidence_note: str


class RiskTaskOut(BaseModel):
    id: int
    title: str
    status: str
    priority: str
    type: str
    assignee_name: Optional[str]
    due_date: Optional[datetime]
    risk_score: float
    risk_label: str