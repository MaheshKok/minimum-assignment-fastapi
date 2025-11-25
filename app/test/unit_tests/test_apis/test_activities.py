"""
API tests for activities endpoints following kkb_fastapi pattern.
"""

import pytest

from app.test.factory.activity import (
    AirTravelActivityFactory,
    ElectricityActivityFactory,
    GoodsServicesActivityFactory,
)
from app.utils.constants import ActivityType


@pytest.mark.asyncio
async def test_list_electricity_activities(test_async_client):
    """Test listing electricity activities."""
    # Create test activities
    await ElectricityActivityFactory()
    await ElectricityActivityFactory()

    response = await test_async_client.get("/api/v1/activities/electricity")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all(item["activity_type"] == ActivityType.ELECTRICITY for item in data)


@pytest.mark.asyncio
async def test_list_air_travel_activities(test_async_client):
    """Test listing air travel activities."""
    # Create test activities
    await AirTravelActivityFactory()
    await AirTravelActivityFactory()

    response = await test_async_client.get("/api/v1/activities/air-travel")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all(item["activity_type"] == ActivityType.AIR_TRAVEL for item in data)


@pytest.mark.asyncio
async def test_list_goods_services_activities(test_async_client):
    """Test listing goods & services activities."""
    # Create test activities
    await GoodsServicesActivityFactory()
    await GoodsServicesActivityFactory()

    response = await test_async_client.get("/api/v1/activities/goods-services")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all(item["activity_type"] == ActivityType.GOODS_SERVICES for item in data)


@pytest.mark.asyncio
async def test_get_electricity_activity_by_id(test_async_client):
    """Test retrieving specific electricity activity."""
    activity = await ElectricityActivityFactory()

    response = await test_async_client.get(f"/api/v1/activities/electricity/{activity.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(activity.id)
    assert data["country"] == activity.country


@pytest.mark.asyncio
async def test_pagination_electricity_activities(test_async_client):
    """Test pagination for electricity activities."""
    # Create 15 test activities
    for _ in range(15):
        await ElectricityActivityFactory()

    # Get first page
    response = await test_async_client.get("/api/v1/activities/electricity?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10

    # Get second page
    response = await test_async_client.get("/api/v1/activities/electricity?skip=10&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
