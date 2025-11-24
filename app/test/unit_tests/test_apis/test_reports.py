"""
API tests for reports endpoint following kkb_fastapi pattern.
"""

import pytest

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
async def test_generate_empty_emissions_report(test_async_client):
    """Test generating emissions report with no data."""
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    assert "summary" in data
    assert "results" in data
    assert "breakdown_by_activity_type" in data

    summary = data["summary"]
    assert float(summary["total_co2e_tonnes"]) == 0.0
    assert summary["total_activities"] == 0


@pytest.mark.asyncio
async def test_generate_emissions_report_with_data(test_async_client):
    """Test generating emissions report with calculated emissions."""
    # Create factors
    await ElectricityEmissionFactorFactory(
        lookup_identifier="United Kingdom", co2e_factor=0.3
    )
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )

    # Create activities
    activity1 = await ElectricityActivityFactory(
        country="United Kingdom", usage_kwh=1000.0
    )
    activity2 = await AirTravelActivityFactory(
        distance_miles=500.0, flight_range="Short-haul", passenger_class="Economy class"
    )

    # Calculate emissions
    payload = {
        "activity_ids": [str(activity1.id), str(activity2.id)],
        "recalculate": False,
    }
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Generate report
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    assert len(data["results"]) == 2
    assert data["summary"]["total_activities"] == 2
    assert float(data["summary"]["total_co2e_tonnes"]) > 0


@pytest.mark.asyncio
async def test_report_breakdown_by_activity_type(test_async_client):
    """Test that report includes breakdown by activity type."""
    # Create factors
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    await GoodsServicesEmissionFactorFactory(
        lookup_identifier="Category 0", co2e_factor=0.5
    )

    # Create activities
    activity1 = await ElectricityActivityFactory(usage_kwh=1000.0)
    activity2 = await GoodsServicesActivityFactory(spend_gbp=1000.0)

    # Calculate emissions
    payload = {
        "activity_ids": [str(activity1.id), str(activity2.id)],
        "recalculate": False,
    }
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Generate report
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    breakdown = data["breakdown_by_activity_type"]

    # Should have breakdown for both activity types
    assert "electricity" in breakdown
    assert "goods_services" in breakdown
    assert float(breakdown["electricity"]) > 0
    assert float(breakdown["goods_services"]) > 0


@pytest.mark.asyncio
async def test_report_scope_2_emissions(test_async_client):
    """Test that report correctly aggregates Scope 2 emissions."""
    # Create electricity factor (Scope 2)
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )

    # Create activity
    activity = await ElectricityActivityFactory(usage_kwh=1000.0)

    # Calculate emissions
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Generate report
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    summary = data["summary"]

    assert float(summary["scope_2_tonnes"]) > 0
    assert float(summary["scope_3_tonnes"]) == 0


@pytest.mark.asyncio
async def test_report_scope_3_emissions(test_async_client):
    """Test that report correctly aggregates Scope 3 emissions."""
    # Create air travel factor (Scope 3, Category 6)
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )

    # Create activity
    activity = await AirTravelActivityFactory(
        distance_miles=500.0, flight_range="Short-haul", passenger_class="Economy class"
    )

    # Calculate emissions
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Generate report
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    summary = data["summary"]

    assert float(summary["scope_2_tonnes"]) == 0
    assert float(summary["scope_3_tonnes"]) > 0
    assert float(summary["scope_3_category_6_tonnes"]) > 0


@pytest.mark.asyncio
async def test_report_scope_3_category_1_emissions(test_async_client):
    """Test that report correctly aggregates Scope 3 Category 1 emissions."""
    # Create goods/services factor (Scope 3, Category 1)
    await GoodsServicesEmissionFactorFactory(
        lookup_identifier="Category 0", co2e_factor=0.5
    )

    # Create activity
    activity = await GoodsServicesActivityFactory(spend_gbp=1000.0)

    # Calculate emissions
    payload = {"activity_ids": [str(activity.id)], "recalculate": False}
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Generate report
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    summary = data["summary"]

    assert float(summary["scope_3_tonnes"]) > 0
    assert float(summary["scope_3_category_1_tonnes"]) > 0
    assert float(summary["scope_3_category_6_tonnes"]) == 0


@pytest.mark.asyncio
async def test_report_total_emissions(test_async_client):
    """Test that report calculates total emissions correctly."""
    # Create factors for different scopes
    await ElectricityEmissionFactorFactory(
        lookup_identifier="Test Country 0", co2e_factor=0.3
    )
    await AirTravelEmissionFactorFactory(
        lookup_identifier="Short-haul, Economy class", co2e_factor=0.15
    )

    # Create activities
    activity1 = await ElectricityActivityFactory(usage_kwh=1000.0)
    activity2 = await AirTravelActivityFactory(distance_miles=500.0)

    # Calculate emissions
    payload = {
        "activity_ids": [str(activity1.id), str(activity2.id)],
        "recalculate": False,
    }
    await test_async_client.post("/api/v1/calculations/calculate", json=payload)

    # Generate report
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    summary = data["summary"]

    # Total should equal sum of Scope 2 and Scope 3
    total = float(summary["total_co2e_tonnes"])
    scope_2 = float(summary["scope_2_tonnes"])
    scope_3 = float(summary["scope_3_tonnes"])

    assert abs(total - (scope_2 + scope_3)) < 0.01  # Account for floating point precision


@pytest.mark.asyncio
async def test_report_includes_calculation_date(test_async_client):
    """Test that report includes calculation date."""
    response = await test_async_client.get("/api/v1/reports/emissions")
    assert response.status_code == 200

    data = response.json()
    assert "calculation_date" in data["summary"]
