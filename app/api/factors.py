"""
Emission Factors API router.

CRUD operations for emission factors.
"""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.database.schemas import EmissionFactorDBModel
from app.pydantic_models.emission_factor import (
    EmissionFactorPydModel,
    EmissionFactorCreate,
    EmissionFactorUpdate,
)

router = APIRouter(
    prefix="/api/v1/factors",
    tags=["Emission Factors"],
)

logger = logging.getLogger(__name__)


@router.get("/", response_model=List[EmissionFactorPydModel])
async def list_emission_factors(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """
    List all emission factors with pagination.
    """
    stmt = select(EmissionFactorDBModel).offset(skip).limit(limit)
    result = await session.execute(stmt)
    factors = result.scalars().all()
    return factors


@router.get("/{factor_id}", response_model=EmissionFactorPydModel)
async def get_emission_factor(
    factor_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get emission factor by ID.
    """
    stmt = select(EmissionFactorDBModel).where(EmissionFactorDBModel.id == factor_id)
    result = await session.execute(stmt)
    factor = result.scalars().first()

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
    factor_db = EmissionFactorDBModel(**factor_data.model_dump())
    session.add(factor_db)
    await session.flush()
    await session.refresh(factor_db)

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
    stmt = select(EmissionFactorDBModel).where(EmissionFactorDBModel.id == factor_id)
    result = await session.execute(stmt)
    factor = result.scalars().first()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission factor {factor_id} not found",
        )

    # Update fields
    for field, value in factor_data.model_dump(exclude_unset=True).items():
        setattr(factor, field, value)

    await session.flush()
    await session.refresh(factor)

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
    stmt = select(EmissionFactorDBModel).where(EmissionFactorDBModel.id == factor_id)
    result = await session.execute(stmt)
    factor = result.scalars().first()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission factor {factor_id} not found",
        )

    await session.delete(factor)
    logger.info(f"Deleted emission factor: {factor_id}")
