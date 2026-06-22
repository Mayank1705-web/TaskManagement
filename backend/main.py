from fastapi import FastAPI

from database import engine
import models
from routers import auth, projects, tasks

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TaskFlow DS — Task Manager with Data Science & ML")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}