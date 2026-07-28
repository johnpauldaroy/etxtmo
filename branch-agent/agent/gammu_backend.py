from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_OUT_PREFIX = "OUT"
_IN_PATTERN = re.compile(
    r"^IN(?P<date>\d{8})_(?P<time>\d{6})_(?P<serial>\d+)_(?P<sender>.+)_(?P<sequence>\d+)\.\w+$",
)

# gammu-smsd logs this when it can't open the modem's serial port at all
# (unplugged, wrong port, driver gone) -- distinct from transient send/status
# errors ("Error getting SMS status", timeouts) that can happen even with a
# healthy connection. "Starting phone communication..." precedes *every*
# connection attempt (successful or not), so it can't be used as a recovery
# signal on its own -- only whether a connection-error line follows it.
_CONNECTION_ATTEMPT_MARKER = "Starting phone communication"
_CONNECTION_ERROR_MARKERS = (
    "Error opening device",
    "Error at init connection",
)


class GammuBackend:
    """
    Adapter for Gammu SMSD's `files` service: https://docs.gammu.org/smsd/files.html

    Gammu SMSD owns the actual modem send/receive; this class only reads and
    writes the spool folders it watches (outbox/sent/error/inbox), plus a small
    local SQLite cursor table to track which spool files have already been
    relayed to the central API (idempotency across agent restarts).
    """

    def __init__(
        self,
        *,
        outbox_path: str,
        sent_path: str,
        error_path: str,
        inbox_path: str,
        cursor_db_path: str,
        smsd_log_path: str | None = None,
    ) -> None:
        self.outbox_path = Path(outbox_path)
        self.sent_path = Path(sent_path)
        self.error_path = Path(error_path)
        self.inbox_path = Path(inbox_path)
        for path in (self.outbox_path, self.sent_path, self.error_path, self.inbox_path):
            path.mkdir(parents=True, exist_ok=True)

        self.smsd_log_path = Path(smsd_log_path) if smsd_log_path else None

        self.conn = sqlite3.connect(cursor_db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self.conn.close()

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS tb_processed_outcome (filename TEXT PRIMARY KEY)")
        cur.execute("CREATE TABLE IF NOT EXISTS tb_processed_inbox (filename TEXT PRIMARY KEY)")
        self.conn.commit()

    def _already_processed(self, table: str, filename: str) -> bool:
        row = self.conn.execute(f"SELECT filename FROM {table} WHERE filename = ?", (filename,)).fetchone()
        return row is not None

    def _mark_processed(self, table: str, filename: str) -> None:
        self.conn.execute(f"INSERT OR IGNORE INTO {table} (filename) VALUES (?)", (filename,))
        self.conn.commit()

    def enqueue_outbound(self, *, queue_id: str, phone_number: str, message_body: str) -> None:
        safe_phone = re.sub(r"[^0-9+]", "", phone_number)
        now = datetime.now()
        filename = (
            f"{_OUT_PREFIX}A{now:%Y%m%d_%H%M%S}_{now.microsecond:06d}_"
            f"{safe_phone}_{queue_id}.txt"
        )
        target = self.outbox_path / filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(message_body, encoding="utf-8")
        temporary.replace(target)

    def fetch_delivery_updates(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for entry in sorted(self.sent_path.glob(f"{_OUT_PREFIX}*.txt")):
            if self._already_processed("tb_processed_outcome", entry.name):
                continue
            queue_id = self._extract_queue_id(entry.name)
            if queue_id:
                results.append(
                    {
                        "queue_id": queue_id,
                        "status": "sent",
                        "external_message_id": entry.name,
                        "error_message": None,
                    },
                )
            self._mark_processed("tb_processed_outcome", entry.name)

        for entry in sorted(self.error_path.glob(f"{_OUT_PREFIX}*.txt")):
            if self._already_processed("tb_processed_outcome", entry.name):
                continue
            queue_id = self._extract_queue_id(entry.name)
            if queue_id:
                results.append(
                    {
                        "queue_id": queue_id,
                        "status": "failed",
                        "external_message_id": None,
                        "error_message": "Gammu SMSD reported a send error",
                    },
                )
            self._mark_processed("tb_processed_outcome", entry.name)

        return results

    @staticmethod
    def _extract_queue_id(filename: str) -> str | None:
        # Gammu FILES format:
        # OUT<priority><date>_<time>_<serial>_<recipient>_<note>.txt
        # The central queue UUID is stored in the arbitrary note field.
        body = Path(filename).stem
        _, separator, queue_id = body.rpartition("_")
        if not separator:
            return None
        return queue_id or None

    def fetch_incoming_messages(self) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str, str], dict[int, Path]] = {}
        unmatched: list[Path] = []

        for entry in sorted(self.inbox_path.glob("IN*.txt")):
            if self._already_processed("tb_processed_inbox", entry.name):
                continue
            match = _IN_PATTERN.match(entry.name)
            if not match:
                unmatched.append(entry)
                continue
            key = (match.group("date"), match.group("time"), match.group("serial"), match.group("sender"))
            groups.setdefault(key, {})[int(match.group("sequence"))] = entry

        items: list[dict[str, Any]] = []
        for (date_part, time_part, _serial, sender), parts in groups.items():
            ordered_paths = [parts[sequence] for sequence in sorted(parts)]
            message_text = "".join(path.read_text(encoding="utf-8", errors="replace") for path in ordered_paths)
            received_at = _parse_inbox_timestamp(date_part, time_part)
            items.append(
                {
                    "phone_number": sender,
                    "message_text": message_text,
                    "received_at": received_at,
                    "raw_payload": {"files": [path.name for path in ordered_paths]},
                },
            )
            for path in ordered_paths:
                self._mark_processed("tb_processed_inbox", path.name)

        for path in unmatched:
            items.append(
                {
                    "phone_number": "unknown",
                    "message_text": path.read_text(encoding="utf-8", errors="replace"),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "raw_payload": {"files": [path.name]},
                },
            )
            self._mark_processed("tb_processed_inbox", path.name)

        return items

    def is_modem_reachable(self, *, tail_bytes: int = 8192) -> bool:
        """Infer modem connectivity from gammu-smsd's own log instead of
        probing the port ourselves -- gammu-smsd holds the COM port
        exclusively while running, so a second process trying to open it
        (e.g. `gammu identify`) always fails with "already opened by
        another app" regardless of whether the modem itself is reachable.

        Scans the tail of the log for the most recent connection attempt
        ("Starting phone communication...", logged before every attempt,
        successful or not) and checks whether a connection-error line
        immediately follows it. Returns True (assume reachable) if no
        smsd_log_path is configured or the log doesn't exist yet, so
        branch PCs that haven't set this up keep prior behavior."""
        if not self.smsd_log_path or not self.smsd_log_path.exists():
            return True

        try:
            with self.smsd_log_path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - tail_bytes))
                tail = handle.read().decode("utf-8", errors="replace")
        except OSError:
            return True

        lines = tail.splitlines()
        last_attempt_index = None
        for index in range(len(lines) - 1, -1, -1):
            if _CONNECTION_ATTEMPT_MARKER in lines[index]:
                last_attempt_index = index
                break
        if last_attempt_index is None:
            return True

        for line in lines[last_attempt_index:]:
            if any(marker in line for marker in _CONNECTION_ERROR_MARKERS):
                return False
        return True

    def simulate_send_once(self, *, limit: int = 50) -> int:
        """
        Development helper: move queued outbox files straight to sent/ without a
        real modem. Keep disabled in production where Gammu SMSD handles send.
        """
        processed = 0
        for entry in sorted(self.outbox_path.glob(f"{_OUT_PREFIX}*.txt"))[:limit]:
            target = self.sent_path / entry.name
            entry.replace(target)
            processed += 1
        return processed


def _parse_inbox_timestamp(date_part: str, time_part: str) -> str:
    try:
        parsed = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
        return parsed.isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()
