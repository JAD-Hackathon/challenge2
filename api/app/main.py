from app.api.deps import SessionDep
from fastapi import FastAPI
from sqlalchemy import text

app = FastAPI()


@app.get("/health/db")
def health_db(db: SessionDep):
    db.execute(text("SELECT 1"))
    return {"database": "ok"}
