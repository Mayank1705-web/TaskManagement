"""
Tasktopus — conversational AI that talks through a goal with the user,
then proposes a task breakdown (solo or team) and, on approval, creates
real Task rows.

Two endpoints:
  POST /api/tasktopus/chat     — one turn of conversation; may return a plan
  POST /api/tasktopus/approve  — turn an approved plan into real Task rows
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth_core import get_current_user
from openai_client import chat_turn

router = APIRouter(prefix="/api/tasktopus", tags=["tasktopus"])


def _team_context(db: Session, project_id: int) -> str:
    """
    Builds a short, human-readable team roster string for the system/user
    context: name, stack, and CURRENT open-task count (workload), so the
    model can reason about both fit and load — not just fit.
    """
    users = db.query(models.User).all()
    if len(users) <= 1:
        return "No team — this is a solo workspace. Treat every breakdown as solo."

    lines = []
    for u in users:
        open_count = (
            db.query(models.Task)
            .filter(models.Task.assignee_id == u.id, models.Task.status.in_(["todo", "in_progress"]))
            .count()
        )
        lines.append(f"- id={u.id}, name={u.name}, stack={u.stack}, open_tasks={open_count}")
    return "Team roster (id, name, stack, current open task count):\n" + "\n".join(lines)


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    # Inject team context as a system-style user message right before the live conversation,
    # so the model always reasons with up-to-date roster + workload data on every turn.
    context_msg = {
        "role": "user",
        "content": f"[context — not visible to the human] Project: {project.name}. {_team_context(db, payload.project_id)}",
    }

    history = [context_msg] + [{"role": m.role, "content": m.content} for m in payload.messages]
    result = chat_turn(history)

    if result["type"] == "plan":
        plan = result["plan"]
        # Attach human-readable assignee names for the frontend, and validate
        # that any assignee_id the model invented actually exists.
        for t in plan.get("tasks", []):
            t.setdefault("assignee_id", None)
            if t["assignee_id"] is not None:
                assignee = db.query(models.User).filter(models.User.id == t["assignee_id"]).first()
                if not assignee:
                    t["assignee_id"] = None
                    t["assignee_name"] = None
                else:
                    t["assignee_name"] = assignee.name
            else:
                t["assignee_name"] = None
        return schemas.ChatResponse(type="plan", plan=schemas.DelegationPlan(**plan))

    return schemas.ChatResponse(type="text", content=result["content"])


@router.post("/approve")
def approve_plan(payload: schemas.ApprovePlanRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    created_ids = []
    for t in payload.plan.tasks:
        assignee_id = t.assignee_id
        if assignee_id is not None:
            exists = db.query(models.User).filter(models.User.id == assignee_id).first()
            if not exists:
                assignee_id = None  # don't trust client-sent IDs blindly even on approval

        task = models.Task(
            title=t.title,
            description=t.description,
            type=t.type,
            priority=t.priority,
            estimate_hours=t.estimate_hours,
            assignee_id=assignee_id,
            project_id=payload.project_id,
            reporter_id=user.id,
            status="todo",
            ai_generated=True,
        )
        db.add(task)
        db.flush()  # get task.id without a full commit yet
        created_ids.append(task.id)

    db.commit()
    return {"created_task_ids": created_ids, "count": len(created_ids)}