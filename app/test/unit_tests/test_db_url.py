from app.core.config import ConfigFile, get_config
from app.database.base import get_db_url


def test_database_url_env_overrides_config(monkeypatch):
    # Heroku hands the app a postgres:// URL and may rotate its credentials.
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db.example.com:5432/heroku_db")

    url = get_db_url(get_config(ConfigFile.DEVELOPMENT))

    assert url.drivername == "postgresql+asyncpg"
    assert (url.host, url.port, url.database, url.username, url.password) == (
        "db.example.com",
        5432,
        "heroku_db",
        "u",
        "p",
    )
    # Without this, asyncpg's default "prefer" silently falls back to plaintext.
    assert url.query["ssl"] == "require"


def test_config_db_used_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    url = get_db_url(get_config(ConfigFile.DEVELOPMENT))

    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "localhost"


def test_explicit_ssl_in_database_url_is_kept(monkeypatch):
    # A stronger mode such as verify-full must not be downgraded to require.
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db.example.com:5432/d?ssl=verify-full")

    url = get_db_url(get_config(ConfigFile.DEVELOPMENT))

    assert url.query["ssl"] == "verify-full"
