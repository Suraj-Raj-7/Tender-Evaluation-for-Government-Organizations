# App entry point & Router registration
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.db import engine, Base, init_db, SessionLocal
from app.routers import auth, tenders, bidders, criteria, evaluation, reports

app = FastAPI(title="CRPF Tender Evaluation System")

@app.on_event("startup")
def on_startup():
    from app import models
    # This line creates the tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Optional: Seed the database if needed
    from app.seed import run_seed
    db = SessionLocal() 
    try:
        run_seed(db)
    finally:
        db.close()
    print("Database initialized and schema updated.")
    
# Register all API Routers
app.include_router(auth.router)
app.include_router(tenders.router)
app.include_router(criteria.router)
app.include_router(bidders.router)
app.include_router(evaluation.router, prefix="/api/evaluation")
app.include_router(reports.router)

# Serve the static frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Main entry point for the frontend
@app.get("/")
async def root():
    return FileResponse("app/static/index.html")