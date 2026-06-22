"""
Analytics endpoints. Each chart endpoint:
  1. Pulls relevant rows via SQLAlchemy
  2. Loads into a pandas DataFrame
  3. Renders a seaborn/matplotlib PNG to backend/static/charts/
  4. Returns the chart's relative URL + any summary stats as JSON

Frontend just does <img src="..."> with the returned url.
"""

import os
import uuid
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # headless rendering, required on a server
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
from database import get_db
from auth_core import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

CHART_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "charts")
os.makedirs(CHART_DIR, exist_ok=True)

sns.set_theme(style="whitegrid", palette="muted")


def _save_fig(fig, name_prefix: str) -> str:
    fname = f"{name_prefix}_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(CHART_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return f"/static/charts/{fname}"

@router.get("/burndown/{sprint_id}")
def sprint_burndown(sprint_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    sprint = db.query(models.Sprint).filter(models.Sprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(404, "Sprint not found")

    tasks = db.query(models.Task).filter(models.Task.sprint_id == sprint_id).all()
    if not tasks:
        raise HTTPException(400, "No tasks in this sprint yet")

    df = pd.DataFrame([{
        "estimate_hours": t.estimate_hours,
        "completed_at": t.completed_at,
        "status": t.status,
    } for t in tasks])

    total_hours = df["estimate_hours"].sum()
    days = pd.date_range(sprint.start_date.date(), sprint.end_date.date(), freq="D")

    # Ideal burndown: straight line from total_hours to 0
    ideal = pd.Series(
        [total_hours - (total_hours / (len(days) - 1)) * i for i in range(len(days))],
        index=days,
    ) if len(days) > 1 else pd.Series([total_hours, 0], index=[days[0], days[0]])

    # Actual burndown: remaining hours after each day's completions
    remaining = total_hours
    actual_vals = []
    for day in days:
        completed_today = df[
            (df["completed_at"].notna()) & (pd.to_datetime(df["completed_at"]).dt.date == day.date())
        ]["estimate_hours"].sum()
        remaining -= completed_today
        actual_vals.append(max(remaining, 0))
    actual = pd.Series(actual_vals, index=days)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(ideal.index, ideal.values, "--", color="#94a3b8", label="Ideal", linewidth=2)
    ax.plot(actual.index, actual.values, "o-", color="#6366f1", label="Actual", linewidth=2.5)
    ax.set_title(f"Sprint Burndown — {sprint.name}", fontsize=13, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Remaining estimated hours")
    ax.legend()
    fig.autofmt_xdate(rotation=30)

    url = _save_fig(fig, "burndown")

    done = len(df[df["status"] == "done"])
    return {
        "chart_url": url,
        "total_tasks": len(tasks),
        "done_tasks": done,
        "total_hours": round(total_hours, 1),
        "remaining_hours": round(float(actual.iloc[-1]), 1),
    }

@router.get("/velocity/{project_id}")
def velocity(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    sprints = db.query(models.Sprint).filter(models.Sprint.project_id == project_id).order_by(models.Sprint.start_date).all()
    if not sprints:
        raise HTTPException(400, "No sprints found for this project")

    rows = []
    for s in sprints:
        tasks = db.query(models.Task).filter(models.Task.sprint_id == s.id).all()
        committed = sum(t.estimate_hours for t in tasks)
        completed = sum(t.estimate_hours for t in tasks if t.status == "done")
        rows.append({"sprint": s.name, "committed": committed, "completed": completed})

    df = pd.DataFrame(rows)
    df_melt = df.melt(id_vars="sprint", var_name="kind", value_name="hours")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=df_melt, x="sprint", y="hours", hue="kind", ax=ax, palette=["#cbd5e1", "#6366f1"])
    ax.set_title(f"Velocity by Sprint", fontsize=13, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Hours")
    ax.legend(title="")
    plt.xticks(rotation=20, ha="right")

    url = _save_fig(fig, "velocity")
    avg_velocity = round(df["completed"].mean(), 1) if len(df) else 0

    return {"chart_url": url, "avg_velocity_hours": avg_velocity, "sprints": rows}

@router.get("/workload/{project_id}")
def workload_heatmap(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    if not tasks:
        raise HTTPException(400, "No tasks found for this project")

    rows = []
    for t in tasks:
        if not t.assignee:
            continue
        rows.append({
            "assignee": t.assignee.name,
            "status": t.status,
            "hours": t.estimate_hours,
        })

    if not rows:
        raise HTTPException(400, "No assigned tasks found")

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index="assignee", columns="status", values="hours", aggfunc="sum", fill_value=0)

    fig, ax = plt.subplots(figsize=(7, max(3, 0.5 * len(pivot))))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="rocket_r", ax=ax, cbar_kws={"label": "Hours"})
    ax.set_title("Workload by Assignee × Status", fontsize=13, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")

    url = _save_fig(fig, "workload")

    overloaded = pivot.sum(axis=1).sort_values(ascending=False)
    top = overloaded.index[0] if len(overloaded) else None

    return {
        "chart_url": url,
        "most_loaded_assignee": top,
        "totals": overloaded.round(1).to_dict(),
    }

@router.get("/priority-distribution/{project_id}")
def priority_distribution(project_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    if not tasks:
        raise HTTPException(400, "No tasks found")

    df = pd.DataFrame([{"priority": t.priority, "status": t.status} for t in tasks])

    fig, ax = plt.subplots(figsize=(6, 4.5))
    order = ["low", "medium", "high", "urgent"]
    sns.countplot(data=df, x="priority", hue="status", order=[o for o in order if o in df["priority"].unique()], ax=ax)
    ax.set_title("Task Priority Distribution", fontsize=13, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Count")

    url = _save_fig(fig, "priority")
    return {"chart_url": url, "counts": df["priority"].value_counts().to_dict()}

