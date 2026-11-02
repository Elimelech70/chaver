"""Job mechanism (analyst implementation M3): with and without CHAVER_JOB.

Checks the system context, goal, strategy and edge map, and that CHAVER.md is passed
byte-for-byte to the language faculty.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from chaver.archetype.job import JOB_ENV, job_path_from_env, load_job
from chaver.archetype.loader import load_archetype
from chaver.cognitive.executive import Executive
from chaver.cognitive.strategy import StrategyLayer
from chaver.language import faculty as fac
from chaver.state import ChaverState
from chaver.working_memory.ringing import WorkingMemory

ROOT = Path(__file__).resolve().parent.parent
CHAVER_MD = ROOT / "CHAVER.md"
JOB_MD = ROOT / "JOB.md"


class _RecordingBackend(fac._Backend):
    """Fake backend: records what the faculty sends; no network."""

    calls: list[dict] = []

    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def label(self) -> str:
        return f"fake/{self._model}"

    async def generate(self, system_prompt: str, user_content: str, max_tokens: int) -> str:
        _RecordingBackend.calls.append(
            {"system": system_prompt, "user": user_content, "max_tokens": max_tokens})
        return "ok"


@pytest.fixture
def fake_backend(monkeypatch):
    _RecordingBackend.calls = []
    monkeypatch.setitem(fac.BACKENDS, "fake", _RecordingBackend)
    return _RecordingBackend


def _archetype_from_env(monkeypatch, value: str | None):
    if value is None:
        monkeypatch.delenv(JOB_ENV, raising=False)
    else:
        monkeypatch.setenv(JOB_ENV, value)
    p = job_path_from_env(ROOT)
    job = load_job(p) if p is not None else None
    return load_archetype(CHAVER_MD, job=job)


def _tick_stack(archetype):
    state = ChaverState(archetype=archetype, working_memory=WorkingMemory())
    asyncio.run(Executive(state)._tick())
    asyncio.run(StrategyLayer(state)._tick())
    return state


def _speak(archetype, fake_backend) -> str:
    language = fac.LanguageFaculty(archetype=archetype, backend_name="fake", model="m")
    asyncio.run(language.generate(fac.LanguageRequest(prompt="hello")))
    return fake_backend.calls[-1]["system"]


# ── Without a job: unchanged behaviour ──────────────────────────────────────

@pytest.mark.parametrize("value", [None, "", "   "])
def test_no_job_is_unchanged(monkeypatch, fake_backend, value):
    arch = _archetype_from_env(monkeypatch, value)
    assert arch.job is None
    chaver_bytes = CHAVER_MD.read_bytes()
    system = _speak(arch, fake_backend)
    assert system.encode("utf-8") == chaver_bytes  # byte-for-byte, nothing added

    state = _tick_stack(arch)
    assert state.current_goal.intention.startswith("walk alongside Craig")
    assert state.current_goal.context == "foundational purpose from archetype"
    assert state.current_strategy.approach == "attend, remember, reflect, refer"
    assert arch.edge_map.own_domain.startswith("companion, memory")
    assert [n.name for n in arch.edge_map.neighbours] == ["Shomer", "Oz", "Eitan", "Binah", "Tevunah"]


# ── With a job ───────────────────────────────────────────────────────────────

def test_with_job_system_context(monkeypatch, fake_backend):
    arch = _archetype_from_env(monkeypatch, "JOB.md")
    assert arch.job is not None and arch.job.path == JOB_MD
    system = _speak(arch, fake_backend).encode("utf-8")
    chaver_bytes, job_bytes = CHAVER_MD.read_bytes(), JOB_MD.read_bytes()
    assert system.startswith(chaver_bytes)          # CHAVER.md first, unchanged
    assert system.endswith(job_bytes)               # then JOB.md, whole
    assert len(system) == len(chaver_bytes) + len(b"\n\n---\n\n") + len(job_bytes)


def test_with_job_same_text_every_call(monkeypatch, fake_backend):
    arch = _archetype_from_env(monkeypatch, "JOB.md")
    language = fac.LanguageFaculty(archetype=arch, backend_name="fake", model="m")
    for prompt in ("a", "b"):
        asyncio.run(language.generate(fac.LanguageRequest(prompt=prompt, wm_context="x")))
    assert fake_backend.calls[0]["system"] == fake_backend.calls[1]["system"]
    assert language.call_count == 2


def test_with_job_goal_strategy_edges(monkeypatch):
    arch = _archetype_from_env(monkeypatch, "JOB.md")
    job = arch.job
    assert job.goal.startswith("Craig's goal is cash flow")
    assert len(job.processes) >= 3 and job.processes[0].startswith("Daily")
    assert job.own_domain.startswith("analysis for Catalyst Horizon")
    assert "specific trade execution decisions" in job.own_edges
    assert [n.name for n in job.neighbours] == ["Trader", "PM", "Implementer", "Craig"]
    assert "order" in job.neighbours[0].signals

    state = _tick_stack(arch)
    assert state.current_goal.intention == job.goal
    assert state.current_goal.context == "job goal from JOB.md"
    assert state.current_strategy.steps == job.processes
    assert arch.edge_map.own_domain == job.own_domain
    assert arch.edge_map.own_edges == job.own_edges
    assert [n.name for n in arch.edge_map.neighbours] == ["Trader", "PM", "Implementer", "Craig"]


def test_absolute_path_and_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv(JOB_ENV, str(JOB_MD))
    assert job_path_from_env(tmp_path) == JOB_MD
    monkeypatch.setenv(JOB_ENV, "nope.md")
    with pytest.raises(FileNotFoundError):
        load_job(job_path_from_env(tmp_path))


def test_parser_on_minimal_job(tmp_path):
    p = tmp_path / "JOB.md"
    p.write_text(
        "# JOB\n\n## Goal\n\nFind the truth.\n\n## Function and processes\n\n- one\n- two\n  continued\n\n"
        "## Your Edges\n\nOwn domain: testing\n\n- not this\n\n"
        "## Neighbours\n\n- **Ann** — reviewer. Signals: review, check\n- **Bob** — builder.\n",
        encoding="utf-8")
    job = load_job(p)
    assert job.text == p.read_text(encoding="utf-8")
    assert job.goal == "Find the truth."
    assert job.processes == ["one", "two continued"]
    assert job.own_domain == "testing" and job.own_edges == ["not this"]
    assert [(n.name, n.domain, n.signals) for n in job.neighbours] == [
        ("Ann", "reviewer", ["review", "check"]), ("Bob", "builder", [])]
