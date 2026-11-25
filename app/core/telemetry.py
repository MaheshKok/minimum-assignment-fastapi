"""
Send application logs and request metrics to an OTLP backend such as Grafana Cloud.

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set. The exporters read the endpoint, the
OTEL_EXPORTER_OTLP_HEADERS auth header and OTEL_SERVICE_NAME from the environment.
Tracing stays with the New Relic agent: running OpenTelemetry's FastAPI instrumentation
beside it breaks requests (newrelic-python-agent issue #1136).
"""

import logging
import os
import time

from fastapi import FastAPI, Request
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

# The exporter's own logs would feed back into the exporter.
_NOT_SHIPPED = ("opentelemetry", "urllib3", "requests")


def setup_telemetry(
    app: FastAPI,
    metric_reader: MetricReader | None = None,
    log_exporter: LogExporter | None = None,
) -> None:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    resource = Resource.create()

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter or OTLPLogExporter())
    )
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    handler.addFilter(lambda record: not record.name.startswith(_NOT_SHIPPED))
    logging.getLogger().addHandler(handler)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader or PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    duration = meter_provider.get_meter(__name__).create_histogram(
        "http.server.request.duration", unit="s", description="Time to serve a request"
    )

    @app.middleware("http")
    async def record_request_duration(request: Request, call_next):
        start = time.perf_counter()
        status_code = 500  # an exception escaping call_next becomes a 500 response
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            duration.record(
                time.perf_counter() - start,
                {
                    "http.request.method": request.method,
                    # The template, not the raw path, so /items/1 and /items/2 share one series.
                    "http.route": getattr(route, "path", "unmatched"),
                    "http.response.status_code": status_code,
                },
            )
