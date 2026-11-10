"""
FastAPI application factory following kkb_fastapi pattern.

Creates and configures the FastAPI application instance.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    activities_router,
    aggregations_router,
    calculations_router,
    factors_router,
    reports_router,
    summaries_router,
)
from app.core.config import get_config
from app.database.base import engine_kw, get_db_url
from app.database.session_manager.db_session import Database

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logging.error(f"HTTPException occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code, content={"detail": str(exc.detail)}
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    # The text often holds SQL, so it goes to the logs with the traceback, never to the caller.
    logging.exception(f"Unhandled error on {request.method} {request.url.path}", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    # input and ctx can hold values JSON cannot encode (Decimal limits, exceptions, NaN).
    errors = [{k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": errors,
            "message": "Validation error",
        },
    )


def register_routers(app: FastAPI):
    """Register all API routers."""
    app.include_router(factors_router)
    app.include_router(activities_router)
    app.include_router(calculations_router)
    app.include_router(reports_router)
    app.include_router(aggregations_router)
    app.include_router(summaries_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Handles database initialization and cleanup.
    """
    logging.info("Application startup")
    async_db_url = get_db_url(app.state.config)

    Database.init(async_db_url, engine_kw=engine_kw)
    logging.info("Initialized database")

    try:
        yield
    finally:
        logging.info("Application shutdown")


def get_app(config_file: str) -> FastAPI:
    """
    Application factory function.

    Args:
        config_file: Configuration file name (e.g., "production.toml")

    Returns:
        Configured FastAPI application instance
    """
    config = get_config(config_file)

    app = FastAPI(
        title=config.data.get("api", {}).get(
            "title", "Carbon Emissions Calculator API"
        ),
        description=config.data.get("api", {}).get(
            "description", "FastAPI-based carbon emissions calculation engine"
        ),
        version=config.data.get("api", {}).get("version", "1.0.0"),
        debug=config.data.get("api", {}).get("debug", False),
        lifespan=lifespan,
        # Generate better OpenAPI schema for enums
        generate_unique_id_function=lambda route: (
            f"{route.tags[0]}-{route.name}" if route.tags else route.name
        ),
    )

    app.state.config = config

    # Register routers
    register_routers(app)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Set up CORS middleware
    origins = [
        "http://localhost:3000",  # For local development
        "http://127.0.0.1:3000",
        # Add any other origins as needed
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
