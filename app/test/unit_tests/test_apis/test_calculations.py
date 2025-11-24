"""
API tests for calculations endpoint following kkb_fastapi pattern.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import Database
from app.database.schemas import EmissionResultDBModel
from app.test.factory.activity import (
    AirTravelActivityFactory,
    ElectricityActivityFactory,
    GoodsServicesActivityFactory,
)
from app.test.factory.emission_factor import (
    AirTravelEmissionFactorFactory,
    ElectricityEmissionFactorFactory,
    GoodsServicesEmissionFactorFactory,
)


@pytest.mark.asyncio
async def test_calculate_emissions_for_electricity_activity(test_async_client):
    """Test calculating emissions for electricity activity."""
    # Create emission factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    # Calculate emissions
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["activity_id"] == str(activity.id)
    assert "co2e_tonnes" in data[0]
    assert float(data[0]["co2e_tonnes"]) > 0


@pytest.mark.asyncio
async def test_calculate_emissions_for_air_travel_activity(test_async_client):
    """Test calculating emissions for air travel activity."""
    # Create emission factor and activity
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )
    activity = await AirTravelActivityFactory(
        distance_miles=500.0, flight_range="Short-haul", passenger_class="Economy class"
    )

    # Calculate emissions
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["activity_id"] == str(activity.id)
    assert float(data[0]["co2e_tonnes"]) > 0


@pytest.mark.asyncio
async def test_calculate_emissions_for_goods_services_activity(test_async_client):
    """Test calculating emissions for goods & services activity."""
    # Create emission factor and activity
    await GoodsServicesEmissionFactorFactory(
        lookup_identifier="Office Supplies", co2e_factor=0.5
    )
    activity = await GoodsServicesActivityFactory(
        supplier_category="Office Supplies", spend_gbp=1000.0
    )

    # Calculate emissions
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["activity_id"] == str(activity.id)
    assert float(data[0]["co2e_tonnes"]) > 0


@pytest.mark.asyncio
async def test_calculate_emissions_batch(test_async_client):
    """Test calculating emissions for multiple activities in batch."""
    # Create emission factors
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )

    # Create activities
    activity1 = await ElectricityActivityFactory(usage_kwh=1000.0)
    activity2 = await AirTravelActivityFactory(distance_miles=500.0)

    # Calculate emissions for both
    payload = {
        "activity_ids": [str(activity1.id), str(activity2.id)],
        "recalculate": False,
    }

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_recalculate_emissions(test_async_client):
    """Test recalculating emissions for an activity."""
    # Create emission factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    # Calculate first time
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Recalculate
    recalc_payload = {"activity_ids": [str(activity.id)], "recalculate": True}
    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=recalc_payload
    )
    assert response.status_code == 200

    # Should still have only one result
    async with Database() as session:
        stmt = select(EmissionResultDBModel).where(
            EmissionResultDBModel.activity_id == activity.id
        )
        result = await session.execute(stmt)
        results = result.scalars().all()
        assert len(results) == 1


@pytest.mark.asyncio
async def test_calculate_emissions_no_matching_factor(test_async_client):
    """Test calculating emissions when no matching factor exists."""
    # Create activity without corresponding factor
    activity = await ElectricityActivityFactory(country="Nonexistent Country")

    payload = {"activity_ids": [str(activity.id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    # Should return empty list or handle gracefully
    assert len(data) == 0


@pytest.mark.asyncio
async def test_calculate_emissions_invalid_activity_id(test_async_client):
    """Test calculating emissions with invalid activity ID."""
    fake_id = uuid4()
    payload = {"activity_ids": [str(fake_id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 0  # No results for invalid ID


@pytest.mark.asyncio
async def test_calculate_emissions_confidence_score(test_async_client):
    """Test that confidence score is included in calculation results."""
    # Create factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    payload = {"activity_ids": [str(activity.id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert "confidence_score" in data[0]
    # Exact match should have confidence_score of 1.0
    assert float(data[0]["confidence_score"]) == 1.0


@pytest.mark.asyncio
async def test_calculate_emissions_metadata(test_async_client):
    """Test that calculation metadata is included in results."""
    # Create factor and activity
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    activity = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )

    payload = {"activity_ids": [str(activity.id)], "recalculate": False}

    response = await test_async_client.post(
        "/api/v1/calculations/calculate", json=payload
    )
    assert response.status_code == 200

    data = response.json()
    assert "calculation_metadata" in data[0]
    metadata = data[0]["calculation_metadata"]
    assert "usage_kwh" in metadata
    assert "emission_factor_value" in metadata
    assert "calculation_method" in metadata
