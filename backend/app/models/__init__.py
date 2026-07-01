"""
backend/app/models/__init__.py
--------------------------------
Purpose: Imports every model file so that (1) Alembic can discover all
tables when generating migrations, and (2) Base.metadata knows about
every table when init_db() runs.

Why this file exists: SQLAlchemy only registers a table onto Base when
its class definition actually runs (gets imported) somewhere. Importing
every model here, once, guarantees they're all registered no matter
which other file triggers this import.

Note: This file currently only imports User -- we will add one import
line here for every new model file (Tender, Criterion, Bidder, etc.)
as we build them later in Phase 1.
"""

from app.models.user import User, RoleEnum, PasswordResetToken
from app.models.tender import Tender, TenderStatus, TenderEvaluator
from app.models.criterion import Criterion, CriterionCategory, RuleType