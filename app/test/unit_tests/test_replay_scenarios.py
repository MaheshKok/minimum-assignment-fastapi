import importlib.util
from pathlib import Path

_path = Path(__file__).parents[3] / "scripts" / "replay_scenarios.py"
_spec = importlib.util.spec_from_file_location("replay_scenarios", _path)
replay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay)


async def _steady_incidents(monkeypatch, every: float) -> list[str]:
    fired, steps = [], []

    async def no_templates(r):
        return {}

    async def step(r, templates):
        steps.append(1)

    async def incident(r):
        fired.append(r.label)

    monkeypatch.setattr(replay, "load_templates", no_templates)
    monkeypatch.setattr(replay, "normal_step", step)
    runner = replay.Runner(client=None, gap=0)
    # 0.01 minutes is 0.6 seconds of steady traffic.
    await replay.steady(runner, {1: ("1-partial", incident)}, [1], 0.01, 0, every)
    assert steps, "steady traffic sent no normal requests"
    return fired


async def test_incident_every_zero_plants_no_incidents(monkeypatch):
    assert await _steady_incidents(monkeypatch, every=0) == []


async def test_incidents_still_planted_by_default(monkeypatch):
    assert await _steady_incidents(monkeypatch, every=60) == ["1-partial"]
