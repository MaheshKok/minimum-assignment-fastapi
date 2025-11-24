"""
API tests for emission factors endpoint following kkb_fastapi pattern.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import Database
from app.database.schemas import EmissionFactorDBModel
from app.test.factory.emission_factor import EmissionFactorFactory
from app.utils.constants import ActivityType, Scope


@pytest.mark.asyncio
async def test_list_emission_factors_empty(test_async_client):
    """Test listing emission factors when database is empty."""
    response = await test_async_client.get("/api/v1/factors/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_emission_factor(test_async_client):
    """Test creating a new emission factor."""
    payload = {
        "activity_type": ActivityType.ELECTRICITY,
        "lookup_identifier": "United Kingdom",
        "unit": "kWh",
        "co2e_factor": 0.3,
        "scope": Scope.SCOPE_2,
        "category": None,
        "source": "DEFRA 2024",
        "notes": "Test factor",
    }

    response = await test_async_client.post("/api/v1/factors/", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["activity_type"] == ActivityType.ELECTRICITY
    assert data["lookup_identifier"] == "United Kingdom"
    assert float(data["co2e_factor"]) == 0.3
    assert data["scope"] == Scope.SCOPE_2
    assert "id" in data


@pytest.mark.asyncio
async def test_list_emission_factors_with_data(test_async_client):
    """Test listing emission factors with existing data."""
    # Create test factors
    await EmissionFactorFactory()
    await EmissionFactorFactory()
    await EmissionFactorFactory()

    response = await test_async_client.get("/api/v1/factors/")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 3
    assert all("id" in item for item in data)
    assert all("activity_type" in item for item in data)


@pytest.mark.asyncio
async def test_get_emission_factor_by_id(test_async_client):
    """Test retrieving a specific emission factor by ID."""
    # Create test factor
    factor = await EmissionFactorFactory()

    response = await test_async_client.get(f"/api/v1/factors/{factor.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(factor.id)
    assert data["activity_type"] == factor.activity_type
    assert data["lookup_identifier"] == factor.lookup_identifier


@pytest.mark.asyncio
async def test_get_emission_factor_not_found(test_async_client):
    """Test retrieving non-existent emission factor."""
    fake_id = uuid4()
    response = await test_async_client.get(f"/api/v1/factors/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_emission_factor(test_async_client):
    """Test updating an emission factor."""
    # Create test factor
    factor = await EmissionFactorFactory()

    update_payload = {
        "activity_type": factor.activity_type,
        "lookup_identifier": "Updated Country",
        "unit": factor.unit,
        "co2e_factor": 0.7,
        "scope": factor.scope,
        "category": factor.category,
        "source": "Updated Source",
        "notes": "Updated notes",
    }

    response = await test_async_client.put(
        f"/api/v1/factors/{factor.id}", json=update_payload
    )
    assert response.status_code == 200

    data = response.json()
    assert data["lookup_identifier"] == "Updated Country"
    assert float(data["co2e_factor"]) == 0.7
    assert data["source"] == "Updated Source"


@pytest.mark.asyncio
async def test_delete_emission_factor(test_async_client):
    """Test deleting an emission factor."""
    # Create test factor
    factor = await EmissionFactorFactory()

    response = await test_async_client.delete(f"/api/v1/factors/{factor.id}")
    assert response.status_code == 204

    # Verify deletion
    async with Database() as session:
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.id == factor.id
        )
        result = await session.execute(stmt)
        deleted_factor = result.scalars().first()
        assert deleted_factor is None


@pytest.mark.asyncio
async def test_filter_emission_factors_by_activity_type(test_async_client):
    """Test filtering emission factors by activity type."""
    # Create factors for different activity types
    await EmissionFactorFactory(activity_type=ActivityType.ELECTRICITY)
    await EmissionFactorFactory(activity_type=ActivityType.ELECTRICITY)
    await EmissionFactorFactory(activity_type=ActivityType.AIR_TRAVEL)

    response = await test_async_client.get(
        f"/api/v1/factors/?activity_type={ActivityType.ELECTRICITY}"
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all(item["activity_type"] == ActivityType.ELECTRICITY for item in data)


@pytest.mark.asyncio
async def test_filter_emission_factors_by_scope(test_async_client):
    """Test filtering emission factors by GHG scope."""
    # Create factors for different scopes
    await EmissionFactorFactory(scope=Scope.SCOPE_2)
    await EmissionFactorFactory(scope=Scope.SCOPE_2)
    await EmissionFactorFactory(scope=Scope.SCOPE_3)

    response = await test_async_client.get(f"/api/v1/factors/?scope={Scope.SCOPE_2}")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all(item["scope"] == Scope.SCOPE_2 for item in data)
