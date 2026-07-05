"""
backend/app/services/__init__.py
------------------------------------
Empty on purpose. Unlike models/__init__.py, service files don't need
central registration here -- routers and Celery tasks import only the
specific service functions they need.
"""