"""
SQLAlchemy database models (schemas).
"""
from app.database.schemas.emission_factor import EmissionFactorDBModel
from app.database.schemas.activity_data import (
    ElectricityActivityDBModel,
    GoodsServicesActivityDBModel,
    AirTravelActivityDBModel,
)
from app.database.schemas.emission_result import EmissionResultDBModel

__all__ = [
    "EmissionFactorDBModel",
    "ElectricityActivityDBModel",
    "GoodsServicesActivityDBModel",
    "AirTravelActivityDBModel",
    "EmissionResultDBModel",
]
