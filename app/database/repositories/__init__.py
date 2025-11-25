"""
Database repositories for data access layer.

Provides clean abstraction over database operations following repository pattern.
"""
from app.database.repositories.activity import (
    ActivityRepository,
    AirTravelActivityRepository,
    ElectricityActivityRepository,
    GoodsServicesActivityRepository,
)
from app.database.repositories.base import BaseRepository
from app.database.repositories.emission_factor import EmissionFactorRepository
from app.database.repositories.emission_result import EmissionResultRepository
from app.database.repositories.emission_summary import EmissionSummaryRepository

__all__ = [
    "ActivityRepository",
    "AirTravelActivityRepository",
    "BaseRepository",
    "ElectricityActivityRepository",
    "EmissionFactorRepository",
    "EmissionResultRepository",
    "EmissionSummaryRepository",
    "GoodsServicesActivityRepository",
]
