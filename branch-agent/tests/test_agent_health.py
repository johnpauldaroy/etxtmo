from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.main import BranchAgent


def test_unreachable_modem_does_not_pull_jobs() -> None:
    agent = BranchAgent.__new__(BranchAgent)
    agent._modem_reachable = False
    calls: list[str] = []
    agent.pull_and_enqueue_jobs = lambda: calls.append("pull")

    agent.pull_jobs_if_modem_reachable()

    assert calls == []


def test_reachable_modem_pulls_jobs() -> None:
    agent = BranchAgent.__new__(BranchAgent)
    agent._modem_reachable = True
    calls: list[str] = []
    agent.pull_and_enqueue_jobs = lambda: calls.append("pull")

    agent.pull_jobs_if_modem_reachable()

    assert calls == ["pull"]
