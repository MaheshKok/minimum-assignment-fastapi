"""
API routers module.
"""
from app.api.factors import router as factors_router
from app.api.activities import router as activities_router
from app.api.calculations import router as calculations_router
from app.api.reports import router as reports_router

__all__ = [
    "factors_router",
    "activities_router",
    "calculations_router",
    "reports_router",
]
