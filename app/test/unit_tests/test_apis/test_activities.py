"""
API tests for activities endpoints following kkb_fastapi pattern.
"""

import json
from decimal import Decimal

import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.main import validation_exception_handler
from app.pydantic_models.activity import (
    AirTravelActivityCreate,
    ElectricityActivityCreate,
    GoodsServicesActivityCreate,
)
from app.services.calculators.unit_converter import UnitConverter
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


@pytest.mark.asyncio
async def test_create_electricity_activity(test_async_client):
    """Test creating an electricity activity."""
    body = {"date": "2024-01-15", "country": "United Kingdom", "usage_kwh": "1234.5"}

    response = await test_async_client.post("/api/v1/activities/electricity", json=body)
    assert response.status_code == 201

    data = response.json()
    assert data["activity_type"] == ActivityType.ELECTRICITY
    assert data["country"] == body["country"]
    assert Decimal(str(data["usage_kwh"])) == Decimal(body["usage_kwh"])

    response = await test_async_client.get("/api/v1/activities/electricity")
    assert [item["id"] for item in response.json()] == [data["id"]]


@pytest.mark.asyncio
async def test_create_electricity_activity_rejects_negative_usage(test_async_client):
    """Test that a negative usage_kwh is rejected."""
    body = {"date": "2024-01-15", "country": "United Kingdom", "usage_kwh": "-1"}

    response = await test_async_client.post("/api/v1/activities/electricity", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "usage_kwh"]


@pytest.mark.asyncio
async def test_create_air_travel_activity(test_async_client):
    """Test creating an air travel activity computes distance_km like the seeder."""
    body = {
        "date": "2024-01-15",
        "distance_miles": "1000",
        "flight_range": "Long-haul",
        "passenger_class": "Economy",
    }

    response = await test_async_client.post("/api/v1/activities/air-travel", json=body)
    assert response.status_code == 201

    data = response.json()
    assert data["activity_type"] == ActivityType.AIR_TRAVEL
    assert Decimal(str(data["distance_km"])) == UnitConverter.miles_to_km(
        Decimal(body["distance_miles"])
    )

    response = await test_async_client.get("/api/v1/activities/air-travel")
    assert [item["id"] for item in response.json()] == [data["id"]]


@pytest.mark.asyncio
async def test_create_air_travel_activity_rejects_overlong_source_file(test_async_client):
    """A source_file longer than its 255-character column must be a 422, not a database 500."""
    body = {
        "date": "2024-01-15",
        "distance_miles": "100",
        "flight_range": "Short-haul",
        "passenger_class": "Economy",
        "source_file": "x" * 256,
    }

    response = await test_async_client.post("/api/v1/activities/air-travel", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "source_file"]


@pytest.mark.asyncio
async def test_create_air_travel_activity_rejects_negative_distance(test_async_client):
    """Test that a negative distance_miles is rejected."""
    body = {
        "date": "2024-01-15",
        "distance_miles": "-1",
        "flight_range": "Long-haul",
        "passenger_class": "Economy",
    }

    response = await test_async_client.post("/api/v1/activities/air-travel", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "distance_miles"]


@pytest.mark.asyncio
async def test_create_goods_services_activity(test_async_client):
    """Test creating a goods & services activity."""
    body = {
        "date": "2024-01-15",
        "supplier_category": "Office supplies",
        "spend_gbp": "250.00",
    }

    response = await test_async_client.post("/api/v1/activities/goods-services", json=body)
    assert response.status_code == 201

    data = response.json()
    assert data["activity_type"] == ActivityType.GOODS_SERVICES
    assert data["supplier_category"] == body["supplier_category"]
    assert Decimal(str(data["spend_gbp"])) == Decimal(body["spend_gbp"])

    response = await test_async_client.get("/api/v1/activities/goods-services")
    assert [item["id"] for item in response.json()] == [data["id"]]


@pytest.mark.asyncio
async def test_create_goods_services_activity_rejects_negative_spend(test_async_client):
    """Test that a negative spend_gbp is rejected."""
    body = {
        "date": "2024-01-15",
        "supplier_category": "Office supplies",
        "spend_gbp": "-1",
    }

    response = await test_async_client.post("/api/v1/activities/goods-services", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "spend_gbp"]


ELECTRICITY = {"date": "2024-01-15", "country": "United Kingdom", "usage_kwh": "10"}
AIR_TRAVEL = {
    "date": "2024-01-15",
    "distance_miles": "100",
    "flight_range": "Short-haul",
    "passenger_class": "Economy",
}
GOODS = {"date": "2024-01-15", "supplier_category": "Office supplies", "spend_gbp": "10"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("electricity", {**ELECTRICITY, "usage_kwh": "1e30"}),
        ("electricity", {**ELECTRICITY, "country": "United Kingdom\u0000"}),
        # NaN in raw_data is covered by test_production_validation_handler_renders_422: the test
        # app uses FastAPI's default 422 handler, which cannot render NaN, not app.main's.
        ("goods-services", {**GOODS, "spend_gbp": "1e30"}),
        # Fits the miles column, but the derived kilometres do not.
        ("air-travel", {**AIR_TRAVEL, "distance_miles": "99999999"}),
    ],
    ids=["huge-kwh", "nul-in-country", "huge-spend", "km-overflow"],
)
async def test_create_activity_rejects_values_the_database_cannot_store(
    test_async_client, path, body
):
    """Bodies the database would refuse must be a 422, never a 500."""
    response = await test_async_client.post(
        f"/api/v1/activities/{path}",
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "body"),
    [
        (ElectricityActivityCreate, {**ELECTRICITY, "usage_kwh": "1e30"}),
        (ElectricityActivityCreate, {**ELECTRICITY, "country": "United Kingdom\u0000"}),
        (ElectricityActivityCreate, {**ELECTRICITY, "raw_data": {"x": float("nan")}}),
        (GoodsServicesActivityCreate, {**GOODS, "spend_gbp": "1e30"}),
        (AirTravelActivityCreate, {**AIR_TRAVEL, "distance_miles": "99999999"}),
    ],
    ids=["huge-kwh", "nul-in-country", "nan-in-raw-data", "huge-spend", "km-overflow"],
)
async def test_production_validation_handler_renders_422(model, body):
    """The test app lacks app.main's handlers, so call the deployed 422 handler directly."""
    with pytest.raises(ValidationError) as caught:
        model.model_validate(body)

    response = await validation_exception_handler(None, RequestValidationError(caught.value.errors()))

    assert response.status_code == 422

