"""
Seeds the DB with one demo user (login: demo@taskflow.dev / demo1234),
a project, 4 sprints, and ~120 tasks with realistic completion patterns
so the analytics charts and ML models have real signal to work with.

Run from backend/: python seed.py
"""

import random
from datetime import datetime, timedelta

from database import engine, SessionLocal
import models
from auth_core import hash_password

random.seed(42)

models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Reset (idempotent re-seed for a demo project)
db.query(models.Task).delete()
db.query(models.Sprint).delete()
db.query(models.Project).delete()
db.query(models.User).delete()
db.commit()

# ---------- Users ----------
team = [
    {"name": "Aanya Sharma", "email": "aanya@taskflow.dev", "stack": "frontend"},
    {"name": "Rohan Mehta", "email": "rohan@taskflow.dev", "stack": "backend"},
    {"name": "Priya Nair", "email": "priya@taskflow.dev", "stack": "fullstack"},
    {"name": "Karan Verma", "email": "karan@taskflow.dev", "stack": "devops"},
    {"name": "Demo User", "email": "demo@taskflow.dev", "stack": "fullstack"},
]
users = []
for u in team:
    user = models.User(name=u["name"], email=u["email"], hashed_password=hash_password("demo1234"), stack=u["stack"])
    db.add(user)
    users.append(user)
db.commit()
for u in users:
    db.refresh(u)

demo_user = next(u for u in users if u.email == "demo@taskflow.dev")

# ---------- Project ----------
project = models.Project(name="TaskFlow Mobile Revamp", description="Redesign and rebuild the TaskFlow mobile experience.", owner_id=demo_user.id)
db.add(project)
db.commit()
db.refresh(project)

# ---------- Sprints ----------
sprint_count = 4
sprint_len_days = 14
today = datetime.utcnow().date()
project_start = today - timedelta(days=sprint_count * sprint_len_days)

sprints = []
for i in range(sprint_count):
    start = project_start + timedelta(days=i * sprint_len_days)
    end = start + timedelta(days=sprint_len_days - 1)
    sprint = models.Sprint(
        name=f"Sprint {i+1}",
        project_id=project.id,
        start_date=datetime.combine(start, datetime.min.time()),
        end_date=datetime.combine(end, datetime.min.time()),
    )
    db.add(sprint)
    sprints.append(sprint)
db.commit()
for s in sprints:
    db.refresh(s)

# ---------- Tasks ----------
TYPES = ["frontend", "backend", "database", "devops", "design", "testing"]
PRIORITIES = ["low", "medium", "high", "urgent"]

# Each (type) has a different "true" effort distribution and a different
# tendency to run over/under estimate — this is what gives the ML model
# something real to learn.
TYPE_BASE_HOURS = {
    "frontend": 3.5, "backend": 5.0, "database": 4.0,
    "devops": 6.0, "design": 2.5, "testing": 3.0,
}
TYPE_OVERRUN_FACTOR = {  # >1 means tasks tend to take longer than estimated
    "frontend": 1.05, "backend": 1.25, "database": 1.15,
    "devops": 1.4, "design": 0.95, "testing": 1.1,
}
# Some assignees are reliably faster/slower than estimate (drives risk model signal)
ASSIGNEE_SPEED = {u.id: random.uniform(0.85, 1.3) for u in users}

titles_by_type = {
    "frontend": ["Build {x} screen", "Fix layout bug in {x}", "Add animation to {x}", "Refactor {x} component"],
    "backend": ["Implement {x} endpoint", "Optimize {x} query", "Add validation to {x} API", "Fix race condition in {x}"],
    "database": ["Design {x} schema", "Add index on {x} table", "Migrate {x} data", "Write {x} seed script"],
    "devops": ["Set up CI for {x}", "Configure {x} deployment", "Add monitoring for {x}", "Fix {x} pipeline failure"],
    "design": ["Design {x} mockup", "Create {x} icon set", "Update {x} style guide", "Prototype {x} flow"],
    "testing": ["Write unit tests for {x}", "Add integration tests for {x}", "Fix flaky {x} test", "QA pass on {x}"],
}
nouns = ["login", "profile", "kanban board", "notifications", "search", "settings", "onboarding",
         "sprint planner", "comments", "file upload", "dashboard", "billing", "analytics", "export"]

tasks_created = 0
for sprint_idx, sprint in enumerate(sprints):
    is_past_sprint = sprint_idx < sprint_count - 1  # last sprint is "current" -> more open tasks
    n_tasks = random.randint(22, 32)

    for _ in range(n_tasks):
        ttype = random.choice(TYPES)
        priority = random.choices(PRIORITIES, weights=[0.25, 0.4, 0.25, 0.1])[0]
        assignee = random.choice(users)
        noun = random.choice(nouns)
        title = random.choice(titles_by_type[ttype]).format(x=noun)

        base = TYPE_BASE_HOURS[ttype]
        estimate_hours = round(max(0.5, random.gauss(base, base * 0.3)), 1)

        created_offset = random.randint(0, sprint_len_days - 1)
        created_at = datetime.combine(sprint.start_date.date(), datetime.min.time()) + timedelta(days=created_offset, hours=random.randint(8, 17))
        due_date = created_at + timedelta(days=random.randint(2, sprint_len_days))

        # Decide completion status
        if is_past_sprint:
            done_prob = 0.88
        else:
            done_prob = 0.45  # current sprint still in flight

        is_done = random.random() < done_prob

        task_kwargs = dict(
            title=title,
            description=f"{title} as part of the {noun} feature work.",
            priority=priority,
            type=ttype,
            project_id=project.id,
            sprint_id=sprint.id,
            assignee_id=assignee.id,
            reporter_id=demo_user.id,
            ai_generated=random.random() < 0.3,
            estimate_hours=estimate_hours,
            created_at=created_at,
            due_date=due_date,
        )

        if is_done:
            speed = ASSIGNEE_SPEED[assignee.id] * TYPE_OVERRUN_FACTOR[ttype]
            actual_hours = round(max(0.25, random.gauss(estimate_hours * speed, estimate_hours * 0.15)), 1)
            started_at = created_at + timedelta(hours=random.randint(1, 48))
            completed_at = started_at + timedelta(hours=actual_hours, minutes=random.randint(-60, 120))
            # clamp completed_at to not be before started_at
            if completed_at <= started_at:
                completed_at = started_at + timedelta(hours=max(actual_hours, 0.5))
            task_kwargs.update(status="done", actual_hours=actual_hours, started_at=started_at, completed_at=completed_at)
        else:
            if random.random() < 0.55:
                task_kwargs.update(status="in_progress", started_at=created_at + timedelta(hours=random.randint(1, 24)))
            else:
                task_kwargs.update(status="todo")

        db.add(models.Task(**task_kwargs))
        tasks_created += 1

db.commit()

project_id = project.id
sprint_ids = [s.id for s in sprints]
db.close()

print(f"Seed complete: {len(users)} users, 1 project, {len(sprints)} sprints, {tasks_created} tasks.")
print("Login: demo@taskflow.dev / demo1234")
print(f"Project ID: {project_id} | Sprint IDs: {sprint_ids}")