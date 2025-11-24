"""
Emission Factors API router.

CRUD operations for emission factors.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.repositories import EmissionFactorRepository
from app.pydantic_models.emission_factor import (
    EmissionFactorCreate,
    EmissionFactorPydModel,
    EmissionFactorUpdate,
)

router = APIRouter(
    prefix="/api/v1/factors",
    tags=["Emission Factors"],
)

logger = logging.getLogger(__name__)


@router.get("/", response_model=list[EmissionFactorPydModel])
async def list_emission_factors(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all emission factors with pagination.
    """
    repo = EmissionFactorRepository(session)
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


@router.post("/", response_model=EmissionFactorPydModel, status_code=status.HTTP_201_CREATED)
async def create_emission_factor(
    factor_data: EmissionFactorCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Create a new emission factor.
    """
    repo = EmissionFactorRepository(session)
    factor_db = await repo.create(**factor_data.model_dump())

    logger.info(f"Created emission factor: {factor_db.id}")
    return factor_db


@router.put("/{factor_id}", response_model=EmissionFactorPydModel)
async def update_emission_factor(
    factor_id: UUID,
    factor_data: EmissionFactorUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Update an existing emission factor.
    """
    repo = EmissionFactorRepository(session)
    factor = await repo.update(factor_id, **factor_data.model_dump(exclude_unset=True))

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission factor {factor_id} not found",
        )

    logger.info(f"Updated emission factor: {factor_id}")
    return factor


@router.delete("/{factor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emission_factor(
    factor_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Delete an emission factor.
    """
    repo = EmissionFactorRepository(session)
    deleted = await repo.delete(factor_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission factor {factor_id} not found",
        )

    logger.info(f"Deleted emission factor: {factor_id}")
