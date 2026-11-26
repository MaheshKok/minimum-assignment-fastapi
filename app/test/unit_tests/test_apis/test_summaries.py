"""
API tests for the latest-summary endpoint.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.database.schemas import EmissionSummaryDBModel
from app.test.factory.emission_factor import EmissionFactorFactory
from app.test.factory.emission_result import EmissionResultFactory
from app.utils.constants import ActivityType


async def _results(count: int) -> None:
    # The result factory's SubFactory passes the factor object, not its id, so give it the id.
    factor = await EmissionFactorFactory()
    for _ in range(count):
        await EmissionResultFactory(emission_factor_id=factor.id)


def _summary(to_date: date, activity_type: str | None, total: str) -> EmissionSummaryDBModel:
    return EmissionSummaryDBModel(
        from_date=to_date,
        to_date=to_date,
        activity_type=activity_type,
        total_co2e_tonnes=Decimal(total),
        activity_count=3,
        summary_type="daily",
    )


@pytest.mark.asyncio
async def test_latest_summary_returns_newest_and_respects_filter(
    test_async_client, test_db_session
):
    old = _summary(date(2026, 11, 1), ActivityType.ELECTRICITY, "1.5")
    newest = _summary(date(2026, 11, 3), ActivityType.AIR_TRAVEL, "2.25")
    middle = _summary(date(2026, 11, 2), ActivityType.ELECTRICITY, "4.75")
    test_db_session.add_all([old, newest, middle])
    await test_db_session.commit()
    await _results(3)

    response = await test_async_client.get("/api/v1/summaries/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(newest.id)
    assert data["to_date"] == "2026-11-03"
    assert data["activity_type"] == ActivityType.AIR_TRAVEL
    assert Decimal(str(data["total_co2e_tonnes"])) == Decimal("2.25")
    assert data["activity_count"] == 3

    response = await test_async_client.get(
        "/api/v1/summaries/latest", params={"activity": ActivityType.ELECTRICITY}
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(middle.id)


@pytest.mark.asyncio
async def test_latest_summary_is_null_when_no_summaries(test_async_client):
    await _results(1)

    response = await test_async_client.get("/api/v1/summaries/latest")
    assert response.status_code == 200
    assert response.json() is None
