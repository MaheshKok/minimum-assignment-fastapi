"""
API tests for aggregation endpoints.
"""

import pytest

from app.services.aggregators import EmissionAggregator

SECRET = 'relation "emission_summaries" does not exist: SELECT * FROM emission_summaries'


async def _fail(*args, **kwargs):
    raise RuntimeError(SECRET)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "kwargs", "detail"),
    [
        (
            "aggregate_daily_summaries",
            "/api/v1/aggregations/daily",
            {"params": {"target_date": "2025-01-01"}},
            "Failed to aggregate daily emissions",
        ),
        (
            "aggregate_monthly_summaries",
            "/api/v1/aggregations/monthly",
            {"params": {"year": 2025, "month": 1}},
            "Failed to aggregate monthly emissions",
        ),
        (
            "aggregate_custom_range",
            "/api/v1/aggregations/custom",
            {"json": {"aggregation_type": "custom", "from_date": "2025-01-01", "to_date": "2025-01-31"}},
            "Failed to aggregate custom range",
        ),
        (
            "aggregate_daily_summaries",
            "/api/v1/aggregations/backfill",
            {"params": {"from_date": "2025-01-01", "to_date": "2025-01-02"}},
            "Failed to backfill summaries",
        ),
    ],
    ids=["daily", "monthly", "custom", "backfill"],
)
async def test_aggregation_failure_hides_error_text(
    test_async_client, monkeypatch, method, path, kwargs, detail
):
    """A failed aggregation is a 500 whose detail never carries the error text (often SQL)."""
    monkeypatch.setattr(EmissionAggregator, method, _fail)

    response = await test_async_client.post(path, **kwargs)

    assert response.status_code == 500
    assert response.json() == {"detail": detail}
