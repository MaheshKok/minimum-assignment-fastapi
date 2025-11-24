"""
Main FastAPI application entry point.

Following kkb_fastapi pattern.
"""
import logging
import os

import uvicorn
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.create_app import get_app
from app.utils.constants import ConfigFile

logging.basicConfig(level=logging.DEBUG)

app = get_app(ConfigFile.DEVELOPMENT)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logging.error(f"HTTPException occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code, content={"detail": str(exc.detail)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logging.error(f"Exception occurred: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": str(exc)}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "message": "Validation error",
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Carbon Emissions Calculator API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "carbon-emissions-calculator"}


if __name__ == "__main__":
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8000)),
            log_level="debug",
            loop="asyncio",
        )
    except Exception as e:
        logging.error(f"Error running FastAPI: {e}")
