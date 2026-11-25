import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).parents[3] / "scripts" / "mark_deploy.py"
_spec = importlib.util.spec_from_file_location("mark_deploy", _path)
mark_deploy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mark_deploy)

SHA = "50e0dfe7299308145cd68a86415c217944f54ddd"


def _release(version, slug_id):
    return {"version": version, "slug": {"id": slug_id} if slug_id else None}


def test_picks_the_deploy_not_a_later_setting_change_on_the_same_code():
    releases = [_release(20, "new"), _release(17, "new"), _release(16, "new"), _release(15, "old")]
    commits = {"new": SHA, "old": "648d78663970d36f485c1d2a86685800f8291650"}

    assert mark_deploy.deploy_release(releases, commits, SHA)["version"] == 16


def test_no_release_built_from_the_commit_yet():
    releases = [_release(15, "old"), _release(1, None)]

    assert mark_deploy.deploy_release(releases, {"old": "another"}, SHA) is None


def _fake_heroku(monkeypatch, statuses):
    """Each poll of the release list returns the next status for release v16."""
    polls = iter(statuses)
    sleeps = []

    def heroku(path, token, extra_headers=None):
        if path.endswith("/releases"):
            return [{**_release(16, "new"), "status": next(polls)}]
        return {"commit": SHA}

    monkeypatch.setattr(mark_deploy, "heroku", heroku)
    monkeypatch.setattr(mark_deploy.time, "sleep", sleeps.append)
    return sleeps


def test_waits_while_the_release_phase_runs(monkeypatch):
    sleeps = _fake_heroku(monkeypatch, ["pending", "succeeded"])

    assert mark_deploy.wait_for_release("app", "token", SHA)["version"] == 16
    assert sleeps == [mark_deploy.POLL_SECONDS]


def test_a_failed_release_is_never_marked(monkeypatch):
    _fake_heroku(monkeypatch, ["failed"])

    with pytest.raises(RuntimeError, match="v16"):
        mark_deploy.wait_for_release("app", "token", SHA)


def test_marker_time_is_when_the_release_went_live_in_milliseconds():
    release = {"created_at": "2026-11-25T21:30:00Z", "updated_at": "2026-11-25T21:33:30Z"}

    assert mark_deploy.went_live_ms(release) == 1795642410000
