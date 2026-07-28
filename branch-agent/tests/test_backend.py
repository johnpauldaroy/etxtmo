from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.gammu_backend import GammuBackend


def test_enqueue_and_fetch_results(tmp_path: Path):
    backend = make_backend(tmp_path)
    try:
        backend.enqueue_outbound(queue_id="q1", phone_number="+639991111111", message_body="hello")
        queued = list((tmp_path / "outbox").glob("OUT*.txt"))
        assert len(queued) == 1
        assert re.fullmatch(
            r"OUTA\d{8}_\d{6}_\d{6}_\+639991111111_q1\.txt",
            queued[0].name,
        )
        queued[0].replace(tmp_path / "sent" / queued[0].name)
        updates = backend.fetch_delivery_updates()
        assert len(updates) == 1
        assert updates[0]["queue_id"] == "q1"
        assert updates[0]["status"] == "sent"
    finally:
        backend.close()


def test_simulate_send_once_generates_delivery_updates(tmp_path: Path):
    backend = make_backend(tmp_path)
    try:
        backend.enqueue_outbound(queue_id="q2", phone_number="+639992222222", message_body="hello2")
        processed = backend.simulate_send_once(limit=10)
        assert processed == 1

        updates = backend.fetch_delivery_updates()
        assert len(updates) == 1
        assert updates[0]["queue_id"] == "q2"
        assert updates[0]["status"] == "sent"
    finally:
        backend.close()


def make_backend(tmp_path: Path) -> GammuBackend:
    return GammuBackend(
        outbox_path=str(tmp_path / "outbox"),
        sent_path=str(tmp_path / "sent"),
        error_path=str(tmp_path / "error"),
        inbox_path=str(tmp_path / "inbox"),
        cursor_db_path=str(tmp_path / "cursor.sqlite"),
    )
