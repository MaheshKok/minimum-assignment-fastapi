"""
API tests for activities endpoints following kkb_fastapi pattern.
"""
from datetime import date

import pytest

from app.test.factory.activity import (
    AirTravelActivityFactory,
    ElectricityActivityFactory,
    GoodsServicesActivityFactory,
)
from app.utils.constants import ActivityType


@pytest.mark.asyncio
async def test_create_electricity_activity(test_async_client):
    """Test creating an electricity activity."""
    payload = {
        "date": str(date.today()),
        "country": "United Kingdom",
        "usage_kwh": 1500.0,
        "source_file": None,
        "raw_data": {},
    }

    response = await test_async_client.post("/api/v1/activities/electricity", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["country"] == "United Kingdom"
    assert float(data["usage_kwh"]) == 1500.0
    assert data["activity_type"] == ActivityType.ELECTRICITY
    assert "id" in data


@pytest.mark.asyncio
async def test_create_air_travel_activity(test_async_client):
    """Test creating an air travel activity."""
    payload = {
        "date": str(date.today()),
        "distance_miles": 500.0,
        "flight_range": "Short-haul",
        "passenger_class": "Economy class",
        "source_file": None,
        "raw_data": {},
    }

    response = await test_async_client.post("/api/v1/activities/air-travel", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert float(data["distance_miles"]) == 500.0
    assert data["flight_range"] == "Short-haul"
    assert data["activity_type"] == ActivityType.AIR_TRAVEL
    # distance_km should be calculated automatically
    assert "distance_km" in data
    assert float(data["distance_km"]) > 800  # ~804.67 km


@pytest.mark.asyncio
async def test_create_goods_services_activity(test_async_client):
    """Test creating a goods & services activity."""
    payload = {
        "date": str(date.today()),
        "supplier_category": "Office Supplies",
        "spend_gbp": 2500.0,
        "description": "Test purchase",
        "source_file": None,
        "raw_data": {},
    }

    response = await test_async_client.post(
        "/api/v1/activities/goods-services", json=payload
    )
    assert response.status_code == 201

    data = response.json()
    assert data["supplier_category"] == "Office Supplies"
    assert float(data["spend_gbp"]) == 2500.0
    assert data["activity_type"] == ActivityType.GOODS_SERVICES
    assert "id" in data


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
async def test_update_electricity_activity(test_async_client):
    """Test updating an electricity activity."""
    activity = await ElectricityActivityFactory()

    update_payload = {
        "date": str(activity.date),
        "country": "Germany",
        "usage_kwh": 2000.0,
        "source_file": None,
        "raw_data": {},
    }

    response = await test_async_client.put(
        f"/api/v1/activities/electricity/{activity.id}", json=update_payload
    )
    assert response.status_code == 200

    data = response.json()
    assert data["country"] == "Germany"
    assert float(data["usage_kwh"]) == 2000.0


@pytest.mark.asyncio
async def test_delete_electricity_activity(test_async_client):
    """Test soft deleting an electricity activity."""
    activity = await ElectricityActivityFactory()

    response = await test_async_client.delete(
        f"/api/v1/activities/electricity/{activity.id}"
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_create_activity_with_invalid_data(test_async_client):
    """Test creating activity with invalid data."""
    payload = {
        "date": str(date.today()),
        "country": "Test",
        "usage_kwh": -100.0,  # Negative value should fail
    }

    response = await test_async_client.post("/api/v1/activities/electricity", json=payload)
    assert response.status_code == 422  # Validation error


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
