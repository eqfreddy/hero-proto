from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger("tracing")
_initialized = False


def setup_tracing() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    if not settings.otel_endpoint:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("opentelemetry packages not installed — tracing disabled (uv sync --extra otel)")
        return

    resource = Resource.create({"service.name": "hero-proto"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    log.info("tracing initialized endpoint=%s", settings.otel_endpoint)


def instrument_app(app) -> None:
    if not settings.otel_endpoint:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument_app(app)
    except ImportError:
        return
    try:
        from app.db import engine
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception:
        pass
