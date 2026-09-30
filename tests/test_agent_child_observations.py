from __future__ import annotations

from contextlib import contextmanager

import pytest

from app import agent as agent_module
from app.incidents import STATE


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    @contextmanager
    def start(self, name: str, as_type: str = "span", **kwargs):
        record = {"name": name, "as_type": as_type, "kwargs": kwargs, "updates": []}
        self.calls.append(record)

        class Obs:
            def update(self_inner, **u):
                record["updates"].append(u)

        yield Obs()


def _run(monkeypatch, message: str):
    rec = Recorder()
    monkeypatch.setattr(agent_module, "start_observation", rec.start)
    agent_module.LabAgent.run.__wrapped__(
        agent_module.LabAgent(),
        user_id="u1",
        feature="qa",
        session_id="s1",
        message=message,
        correlation_id="req-12345678",
    )
    return rec


def test_retrieval_and_generation_child_observations(monkeypatch) -> None:
    rec = _run(monkeypatch, "Explain monitoring")
    by_name = {c["name"]: c for c in rec.calls}
    assert by_name["retrieval"]["as_type"] == "retriever"
    gen = by_name["llm-generate"]
    assert gen["as_type"] == "generation"
    assert gen["kwargs"]["model"] == "claude-sonnet-4-5"
    update = gen["updates"][-1]
    assert update["usage_details"]["input"] > 0 and update["usage_details"]["output"] > 0
    assert update["cost_details"]["total"] > 0


def test_observations_do_not_capture_raw_input_or_output(monkeypatch) -> None:
    rec = _run(monkeypatch, "email me at secret.person@example.com")
    for call in rec.calls:
        assert "input" not in call["kwargs"]
        for update in call["updates"]:
            assert "input" not in update and "output" not in update
    assert "secret.person@example.com" not in repr(rec.calls)


def test_retrieval_failure_is_marked_error(monkeypatch) -> None:
    monkeypatch.setitem(STATE, "tool_fail", True)
    rec = Recorder()
    monkeypatch.setattr(agent_module, "start_observation", rec.start)
    with pytest.raises(RuntimeError):
        agent_module.LabAgent.run.__wrapped__(
            agent_module.LabAgent(),
            user_id="u1", feature="qa", session_id="s1",
            message="refund", correlation_id="req-12345678",
        )
    retrieval = next(c for c in rec.calls if c["name"] == "retrieval")
    assert retrieval["updates"][-1]["level"] == "ERROR"
