"""
backend/app/database.py
------------------------
Purpose: Sets up the connection to PostgreSQL and provides the tools every
other file needs to talk to the database.

Why this file exists: SQLAlchemy needs three things to work: an 'engine'
(the actual connection), a 'session' (a temporary workspace for one request),
and a 'Base' class (that every table model inherits from). This file creates
all three, once, so nothing else has to repeat this setup.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


# The actual connection pipe to PostgreSQL.
# Built from DATABASE_URL, which we validated in config.py.
engine = create_engine(settings.DATABASE_URL)

# A factory that creates new "session" objects on demand.
# Each session is a temporary workspace for one request's database operations.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    Every table model (User, Tender, Criterion, etc. in Phase 1's models/
    folder) will inherit from this class. SQLAlchemy uses it to know which
    Python classes represent real database tables.
    """
    pass


def get_db():
    """
    Purpose: Hands a fresh database session to whichever route function
    needs it, and guarantees it gets closed afterward -- even if the
    route raises an error.

    Where it's used: Every protected route in routers/ will declare
    'db: Session = Depends(get_db)' as a parameter. FastAPI calls this
    function automatically before running the route.

    Where it gets its data: Calls SessionLocal (defined above), which
    is built from the engine, which is built from settings.DATABASE_URL.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Purpose: Creates all database tables based on every model that inherits
    from Base -- used once at app startup (called from main.py).

    Where it gets its data: Base.metadata knows about every table because
    models/__init__.py will import all model files, which registers each
    table class onto Base automatically.

    Note: In production we rely on Alembic migrations instead of this
    function, but it's useful for quick local testing before migrations
    are set up.
    """
    Base.metadata.create_all(bind=engine)