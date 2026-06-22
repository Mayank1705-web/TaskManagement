from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

import models
import schemas
from database import get_db
from auth_core import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(
    project_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.Task)
    if project_id:
        q = q.filter(models.Task.project_id == project_id)
    if assignee_id:
        q = q.filter(models.Task.assignee_id == assignee_id)
    if status_filter:
        q = q.filter(models.Task.status == status_filter)
    return q.order_by(models.Task.created_at.desc()).all()


@router.get("/my", response_model=list[schemas.TaskOut])
def my_tasks(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Task).filter(models.Task.assignee_id == user.id).all()


@router.post("", response_model=schemas.TaskOut)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    task = models.Task(**payload.dict(), reporter_id=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")

    data = payload.dict(exclude_unset=True)
    new_status = data.get("status")

    # Auto-stamp lifecycle timestamps on status transitions.
    if new_status == "in_progress" and task.started_at is None:
        task.started_at = datetime.utcnow()
    if new_status == "done" and task.completed_at is None:
        task.completed_at = datetime.utcnow()
        if task.started_at and "actual_hours" not in data:
            # Derive actual_hours from elapsed wall-clock time if not explicitly given.
            elapsed = (task.completed_at - task.started_at).total_seconds() / 3600
            task.actual_hours = round(max(elapsed, 0.25), 2)

    for key, value in data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    db.delete(task)
    db.commit()
    return {"ok": True}