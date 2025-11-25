"""
API routers module.
"""
from app.api.activities import router as activities_router
from app.api.aggregations import router as aggregations_router
from app.api.calculations import router as calculations_router
from app.api.factors import router as factors_router
from app.api.reports import router as reports_router
from app.api.summaries import router as summaries_router

__all__ = [
    "activities_router",
    "aggregations_router",
    "calculations_router",
    "factors_router",
    "reports_router",
    "summaries_router",
]
