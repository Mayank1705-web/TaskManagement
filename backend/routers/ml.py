"""
ML endpoints.

1. /estimate  — RandomForestRegressor trained on completed tasks
                (type, priority, assignee) -> actual_hours.
                Retrained on every call from current DB state (dataset is
                small for a student/demo project; this keeps it always
                up to date without a separate training job).

2. /risk      — heuristic + logistic-regression hybrid that scores open
                tasks for "risk of late completion" using historical
                patterns (overdue rate by type/priority/assignee).
"""

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth_core import get_current_user

router = APIRouter(prefix="/api/ml", tags=["ml"])

MIN_TRAINING_ROWS = 8  # below this, fall back to a simple average rather than a flaky model


def _completed_tasks_df(db: Session) -> pd.DataFrame:
    tasks = (
        db.query(models.Task)
        .filter(models.Task.status == "done", models.Task.actual_hours.isnot(None))
        .all()
    )
    return pd.DataFrame([{
        "type": t.type,
        "priority": t.priority,
        "assignee_id": t.assignee_id or -1,
        "actual_hours": t.actual_hours,
    } for t in tasks])


@router.post("/estimate", response_model=schemas.EstimateResponse)
def predict_estimate(payload: schemas.EstimateRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    df = _completed_tasks_df(db)

    if len(df) < MIN_TRAINING_ROWS:
        # Not enough history yet — fall back to the simple average of similar tasks,
        # or a flat default, and say so honestly rather than faking confidence.
        same_type = df[df["type"] == payload.type] if len(df) else df
        fallback = same_type["actual_hours"].mean() if len(same_type) else 4.0
        fallback = round(float(fallback) if not np.isnan(fallback) else 4.0, 1)
        return schemas.EstimateResponse(
            predicted_hours=fallback,
            confidence_note=f"Low confidence — only {len(df)} completed tasks in history. "
                             f"Used average of similar tasks as fallback.",
        )

    le_type = LabelEncoder().fit(df["type"])
    le_priority = LabelEncoder().fit(df["priority"])

    X = pd.DataFrame({
        "type_enc": le_type.transform(df["type"]),
        "priority_enc": le_priority.transform(df["priority"]),
        "assignee_id": df["assignee_id"],
    })
    y = df["actual_hours"]

    model = RandomForestRegressor(n_estimators=80, max_depth=6, random_state=42)
    model.fit(X, y)

    # Handle unseen categories gracefully
    try:
        type_enc = le_type.transform([payload.type])[0]
    except ValueError:
        type_enc = -1
    try:
        priority_enc = le_priority.transform([payload.priority])[0]
    except ValueError:
        priority_enc = -1

    X_pred = pd.DataFrame({
        "type_enc": [type_enc],
        "priority_enc": [priority_enc],
        "assignee_id": [payload.assignee_id or -1],
    })
    pred = float(model.predict(X_pred)[0])

    confidence = "Good" if len(df) >= 25 else "Moderate"
    return schemas.EstimateResponse(
        predicted_hours=round(pred, 1),
        confidence_note=f"{confidence} confidence — model trained on {len(df)} completed tasks.",
    )

@router.get("/risk/{project_id}", response_model=list[schemas.RiskTaskOut])
def risk_scores(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Risk score for OPEN tasks (todo / in_progress) in a project.

    Approach: blend three signals into a 0-1 risk score —
      (a) days until due_date (closer/overdue = riskier)
      (b) historical late-rate for this task's TYPE among completed tasks
      (c) current workload of the assignee (open task count)

    This is intentionally interpretable (no black-box here) since the point
    of this endpoint is to explain *why* a task is flagged, not just flag it.
    """
    open_tasks = (
        db.query(models.Task)
        .filter(models.Task.project_id == project_id, models.Task.status.in_(["todo", "in_progress"]))
        .all()
    )
    if not open_tasks:
        return []

    # Historical late-rate by type, from completed tasks with both due_date and completed_at
    completed = (
        db.query(models.Task)
        .filter(models.Task.project_id == project_id, models.Task.status == "done", models.Task.due_date.isnot(None))
        .all()
    )
    hist_df = pd.DataFrame([{
        "type": t.type,
        "late": 1 if (t.completed_at and t.due_date and t.completed_at > t.due_date) else 0,
    } for t in completed])

    late_rate_by_type = hist_df.groupby("type")["late"].mean().to_dict() if len(hist_df) else {}
    overall_late_rate = hist_df["late"].mean() if len(hist_df) else 0.3  # neutral prior if no history

    # Current open-task load per assignee (for the workload signal)
    load_df = pd.DataFrame([{"assignee_id": t.assignee_id} for t in open_tasks if t.assignee_id])
    load_counts = load_df["assignee_id"].value_counts().to_dict() if len(load_df) else {}
    max_load = max(load_counts.values()) if load_counts else 1

    results = []
    now = datetime.utcnow()
    for t in open_tasks:
        # (a) due-date pressure: 1.0 if overdue, scaling down as due date gets further away
        if t.due_date:
            days_left = (t.due_date - now).total_seconds() / 86400
            due_signal = 1.0 if days_left < 0 else max(0, 1 - days_left / 14)  # 14-day horizon
        else:
            due_signal = 0.4  # no due date set — mild ambiguity penalty

        # (b) historical type late-rate
        type_signal = late_rate_by_type.get(t.type, overall_late_rate)

        # (c) assignee overload
        load_signal = (load_counts.get(t.assignee_id, 0) / max_load) if t.assignee_id else 0.3

        risk = round(0.5 * due_signal + 0.3 * type_signal + 0.2 * load_signal, 2)
        label = "High" if risk >= 0.66 else "Medium" if risk >= 0.4 else "Low"

        results.append(schemas.RiskTaskOut(
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            type=t.type,
            assignee_name=t.assignee.name if t.assignee else None,
            due_date=t.due_date,
            risk_score=risk,
            risk_label=label,
        ))

    results.sort(key=lambda r: r.risk_score, reverse=True)
    return results

