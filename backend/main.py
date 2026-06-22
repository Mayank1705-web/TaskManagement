from fastapi import FastAPI

from database import engine
import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title = "TaskFlow DS - Task Manager with Data Science & ML"
)


@app.get("/api/health")
def health():
    return {
        "status" : "ok"
    }