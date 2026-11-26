"""
Tests for sending logs and request metrics to an OTLP backend (Grafana Cloud).
"""

import logging

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.core.telemetry import setup_telemetry


def _otel_handlers():
    return [h for h in logging.getLogger().handlers if isinstance(h, LoggingHandler)]


@pytest.fixture
def otlp_env(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otlp.invalid/otlp")
    yield
    for handler in _otel_handlers():
        logging.getLogger().removeHandler(handler)


def _duration_points(reader):
    points = []
    for resource_metrics in reader.get_metrics_data().resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == "http.server.request.duration":
                    points.extend(metric.data.data_points)
    return points


async def _get(app, path):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_without_endpoint_nothing_is_added(test_app, monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    middleware_before = list(test_app.user_middleware)

    setup_telemetry(test_app)

    assert test_app.user_middleware == middleware_before
    assert _otel_handlers() == []


@pytest.mark.asyncio
async def test_request_duration_uses_route_template(test_app, otlp_env):
    reader = InMemoryMetricReader()
    setup_telemetry(test_app, metric_reader=reader, log_exporter=InMemoryLogRecordExporter())

    @test_app.get("/items/{item_id}")
    async def item(item_id: int):
        return {"id": item_id}

    response = await _get(test_app, "/items/42")

    assert response.status_code == 200
    (point,) = _duration_points(reader)
    assert point.count == 1
    assert dict(point.attributes) == {
        "http.request.method": "GET",
        "http.route": "/items/{item_id}",
        "http.response.status_code": 200,
    }


@pytest.mark.asyncio
async def test_unhandled_error_is_recorded_as_500(test_app, otlp_env):
    reader = InMemoryMetricReader()
    setup_telemetry(test_app, metric_reader=reader, log_exporter=InMemoryLogRecordExporter())

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    test_app.debug = False
    response = await _get(test_app, "/boom")

    assert response.status_code == 500
    (point,) = _duration_points(reader)
    assert point.attributes["http.response.status_code"] == 500
    assert point.attributes["http.route"] == "/boom"


@pytest.mark.asyncio
async def test_unknown_method_is_recorded_as_other(test_app, otlp_env):
    """Callers pick the method, so each made-up one would otherwise add a metric series."""
    reader = InMemoryMetricReader()
    setup_telemetry(test_app, metric_reader=reader, log_exporter=InMemoryLogRecordExporter())

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.request("FOO1", "/health")

    (point,) = _duration_points(reader)
    assert point.attributes["http.request.method"] == "_OTHER"


@pytest.mark.asyncio
async def test_request_duration_buckets_are_in_seconds(test_app, otlp_env):
    """The SDK's default edges (0, 5, 10, ... 10000) are milliseconds; every request would land
    in the first bucket and p95 would always read 4.75 s."""
    reader = InMemoryMetricReader()
    setup_telemetry(test_app, metric_reader=reader, log_exporter=InMemoryLogRecordExporter())

    await _get(test_app, "/health")

    (point,) = _duration_points(reader)
    assert list(point.explicit_bounds) == [
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1,
        2.5,
        5,
        7.5,
        10,
    ]


def test_app_logs_are_shipped_but_not_exporter_noise(test_app, otlp_env):
    exporter = InMemoryLogRecordExporter()
    setup_telemetry(test_app, metric_reader=InMemoryMetricReader(), log_exporter=exporter)

    logging.getLogger("app.api").info("calculation finished")
    logging.getLogger("app.api").debug("too chatty")
    logging.getLogger("urllib3.connectionpool").warning("retrying export")
    logging.getLogger("opentelemetry.sdk").warning("export failed")
    for handler in _otel_handlers():
        handler.flush()

    bodies = [data.log_record.body for data in exporter.get_finished_logs()]
    assert bodies == ["calculation finished"]
