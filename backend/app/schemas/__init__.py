"""
backend/app/schemas/__init__.py
----------------------------------
Empty on purpose. Unlike models/__init__.py, schemas don't need to be
imported here, since nothing (like Alembic) needs to discover all of
them centrally. Each router imports only the specific schemas it needs.
"""