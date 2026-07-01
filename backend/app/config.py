"""
backend/app/config.py
---------
Purpose: Central place that reads all settings (secrets, URLs, keys) from
the .env file, validates their types using Pydantic, and exposes them as
one 'settings' object.

Why this file exists: Instead of every file in the app calling
os.getenv("DATABASE_URL") separately (error-prone, no type checking),
every other file imports 'settings' from here and gets fully typed,
validated values. This is the single source of truth for configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Defines every environment variable the app needs, with its expected type.
    Pydantic automatically reads matching values from the .env file and
    raises a clear error at startup if something required is missing or
    has the wrong type -- instead of failing randomly later during a request.
    """

    # Database connection string. Used by database.py to connect SQLAlchemy to PostgreSQL.
    DATABASE_URL: str

    # Redis connection string. Used by Celery (background jobs) in later phases.
    REDIS_URL: str

    # Secret key used to sign JWT login tokens. Used by security.py.
    SECRET_KEY: str

    # MinIO (file storage) connection details. Used by storage.py in Phase 2.
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str

    # AI provider keys. Used by llm.py in Phase 3. Optional for now.
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # Password for the very first admin account, created once by seed.py.
    FIRST_ADMIN_PASSWORD: str

    # When True, enables extra debug behavior (e.g. dev-only routes in Phase 2).
    DEBUG: bool = False

    # Tells Pydantic where to find the .env file and how to read it.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Created once when this file is first imported.
# Every other file does: "from app.config import settings"
# and reuses this same validated object -- no need to reload .env repeatedly.
settings = Settings()