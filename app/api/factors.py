"""
Emission Factors API router.

Read-only operations for emission factors.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.repositories import EmissionFactorRepository
from app.pydantic_models.emission_factor import EmissionFactorPydModel

router = APIRouter(
    prefix="/api/v1/factors",
    tags=["Emission Factors"],
)

logger = logging.getLogger(__name__)


@router.get("/", response_model=list[EmissionFactorPydModel])
async def list_emission_factors(
    skip: int = 0,
    limit: int = 100,
    activity_type: str | None = None,
    scope: int | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all emission factors with pagination and optional filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        activity_type: Filter by activity type (optional)
        scope: Filter by GHG scope (optional)
    """
    repo = EmissionFactorRepository(session)

    # Apply filters if provided
    if activity_type:
        factors = await repo.get_by_activity_type(activity_type, skip=skip, limit=limit)
    elif scope is not None:
        factors = await repo.get_by_scope(scope, skip=skip, limit=limit)
    else:
        factors = await repo.get_all(skip=skip, limit=limit)

    return factors


@router.get("/{factor_id}", response_model=EmissionFactorPydModel)
async def get_emission_factor(
    factor_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get emission factor by ID.
    """
    repo = EmissionFactorRepository(session)
    factor = await repo.get_by_id(factor_id)

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission factor {factor_id} not found",
        )

    return factor
