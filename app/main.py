"""
Main FastAPI application entry point.

Following kkb_fastapi pattern.
"""
import logging
import os

import uvicorn

from app.create_app import get_app
from app.utils.constants import ConfigFile

logging.basicConfig(level=logging.DEBUG)

app = get_app(ConfigFile.DEVELOPMENT)


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
