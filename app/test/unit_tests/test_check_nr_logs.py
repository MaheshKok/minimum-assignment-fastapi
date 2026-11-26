import importlib.util
import logging
from pathlib import Path

import pytest

_scripts = Path(__file__).parents[3] / "scripts"


@pytest.fixture
def check(monkeypatch):
    # The script imports its NerdGraph and Heroku helpers from mark_deploy beside it.
    monkeypatch.syspath_prepend(str(_scripts))
    spec = importlib.util.spec_from_file_location("check_nr_logs", _scripts / "check_nr_logs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in {
        "HEROKU_API_KEY": "h",
        "HEROKU_APP_NAME": "app",
        "NEW_RELIC_API_KEY": "n",
        "NEW_RELIC_ACCOUNT_ID": "8740130",
        "LOG_MARKER": "traffic-123-1",
        "MINUTES": "3",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        module, "heroku", lambda path, token: {"NEW_RELIC_APP_NAME": "carbon-emissions-api"}
    )
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    return module


def _counts(monkeypatch, check, marker_counts, deployments=0):
    """Each marker query returns the next count; every query is recorded."""
    marker_counts = iter(marker_counts)
    queries = []

    def count(account_id, nrql, api_key):
        queries.append(nrql)
        if "traffic-123-1" in nrql:
            return next(marker_counts)
        return deployments if "FROM Deployment" in nrql else 42

    monkeypatch.setattr(check, "count", count)
    return queries


def test_marker_found_after_a_wait(monkeypatch, check):
    queries = _counts(monkeypatch, check, [0, 0, 1])

    assert check.main() == 0
    assert not any("FROM Deployment" in q for q in queries)
    assert "WHERE entity.name = 'carbon-emissions-api'" in " ".join(queries)


def test_missing_marker_on_a_readable_account_blames_the_license_key(monkeypatch, check, caplog):
    monkeypatch.setattr(check, "WAIT_SECONDS", 0)
    _counts(monkeypatch, check, [0, 0], deployments=3)

    with caplog.at_level(logging.ERROR):
        assert check.main() == 1
    assert "NEW_RELIC_LICENSE_KEY" in caplog.text


def test_missing_marker_on_an_unreadable_account_blames_the_user_key(monkeypatch, check, caplog):
    monkeypatch.setattr(check, "WAIT_SECONDS", 0)
    _counts(monkeypatch, check, [0, 0], deployments=0)

    with caplog.at_level(logging.ERROR):
        assert check.main() == 1
    assert "NEW_RELIC_API_KEY" in caplog.text


def test_marker_must_be_plain_text(monkeypatch, check):
    monkeypatch.setenv("LOG_MARKER", "x' OR '1'='1")

    with pytest.raises(ValueError):
        check.main()
