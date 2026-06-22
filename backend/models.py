"""
TaskFlow DS — SQLAlchemy models.

Tables:
  User    — auth + profile (name, email, hashed_password, stack)
  Project — top-level container
  Sprint  — time-boxed window within a project
  Task    — unit of work; carries timestamps + actual_hours for analytics/ML
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    stack = Column(String, default="fullstack")  # frontend | backend | fullstack | mobile | devops
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks_assigned = relationship(
        "Task", back_populates="assignee", foreign_keys="Task.assignee_id"
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    sprints = relationship("Sprint", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Sprint(Base):
    __tablename__ = "sprints"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"))
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    project = relationship("Project", back_populates="sprints")
    tasks = relationship("Task", back_populates="sprint")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")

    priority = Column(String, default="medium")   # low | medium | high | urgent
    type = Column(String, default="backend")       # frontend|backend|database|devops|design|testing|mobile
    status = Column(String, default="todo")        # todo|in_progress|done|blocked

    estimate_hours = Column(Float, default=2.0)
    actual_hours = Column(Float, nullable=True)     # filled in when task is marked done

    project_id = Column(Integer, ForeignKey("projects.id"))
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    ai_generated = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="tasks")
    sprint = relationship("Sprint", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks_assigned", foreign_keys=[assignee_id])