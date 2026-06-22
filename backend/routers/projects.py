from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth_core import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Project).all()


@router.post("", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = models.Project(name=payload.name, description=payload.description, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}


# ---------- Sprints (nested under projects) ----------
@router.get("/{project_id}/sprints", response_model=list[schemas.SprintOut])
def list_sprints(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Sprint).filter(models.Sprint.project_id == project_id).all()


@router.post("/{project_id}/sprints", response_model=schemas.SprintOut)
def create_sprint(project_id: int, payload: schemas.SprintCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    sprint = models.Sprint(
        name=payload.name,
        project_id=project_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint