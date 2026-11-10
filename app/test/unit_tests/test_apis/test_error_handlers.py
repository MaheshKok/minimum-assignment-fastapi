"""
Tests for the exception handlers get_app registers.
"""

import pytest
from httpx import ASGITransport, AsyncClient

SECRET = 'relation "users" does not exist: SELECT password FROM users'


@pytest.mark.asyncio
async def test_unhandled_error_hides_exception_text(test_app):
    """A 500 must not hand the exception text (often SQL) to the caller."""

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError(SECRET)

    # Debug mode swaps every 500 handler for a traceback page; production runs without it.
    test_app.debug = False
    # Starlette re-raises after sending the 500; keep the response instead of the exception.
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "SELECT" not in response.text
