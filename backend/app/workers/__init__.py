"""
backend/app/workers/__init__.py
----------------------------------
Empty on purpose. Unlike models/__init__.py, worker files don't need
central registration here -- celery_app.py's 'include' list tells Celery
directly which module (tasks.py) contains the real task functions.
"""