"""
backend/app/main.py
----------------------
Purpose: The actual FastAPI application. Registers every router so
their endpoints become real, callable URLs. Runs database setup and
the admin seed script once, automatically, when the server starts.

Why this file exists: This is the file uvicorn actually runs
(uvicorn app.main:app). Everything else we've built is inert until
it's wired together here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, SessionLocal
from app.seed import run_seed
from app.config import settings
from app.routers import (
    auth, admin, tenders, criteria, bidders, jobs,
    grievances, audit, documents, evaluation,
)

app = FastAPI(title="TenderIQ API", version="1.0.0")

# Allows the React frontend (running on a different port) to call this API.
# Vite's default dev server port is 5173.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registers every router's endpoints onto the running app.
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(tenders.router)
app.include_router(criteria.router)
app.include_router(bidders.router)
app.include_router(jobs.router)
app.include_router(grievances.router)
app.include_router(audit.router)
app.include_router(documents.router)
app.include_router(evaluation.router)

# Only registered when DEBUG=true in .env -- lets us test OCR directly
# without Celery, but is never reachable in a real deployment.
if settings.DEBUG:
    from app.routers import dev_tools
    app.include_router(dev_tools.router)


@app.on_event("startup")
def on_startup():
    """
    Purpose: Runs once, automatically, the moment the server starts.
    Creates all database tables (if they don't exist) and seeds the
    first admin account (if no users exist yet).

    Where it's used: Called by FastAPI itself -- never called manually.
    """
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


@app.get("/")
def health_check():
    """
    Purpose: Simple endpoint to confirm the API is alive and reachable.
    Where it's used: Manual browser check at http://localhost:8000/.
    """
    return {"status": "TenderIQ API is running"}