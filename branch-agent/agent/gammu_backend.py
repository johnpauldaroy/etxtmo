from __future__ import annotations

import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_OUT_PREFIX = "OUT"
_IN_PATTERN = re.compile(
    r"^IN(?P<date>\d{8})_(?P<time>\d{6})_(?P<serial>\d+)_(?P<sender>.+)_(?P<sequence>\d+)\.\w+$",
)

# gammu-smsd logs these when it can't open the modem's serial port at all
# (unplugged, wrong port, driver gone) -- distinct from transient send/status
# errors ("Error getting SMS status", timeouts) that can happen even with a
# healthy connection.
_CONNECTION_ERROR_MARKERS = (
    "Error opening device",
    "Error at init connection",
    "Error setting device speed",
    "Error writing to the device",
    "too many connection errors",
)
# Positive evidence that the last connection attempt actually reached the
# phone, rather than merely "no error logged yet" -- a stuck/endlessly
# retrying SMSD, or one restarted moments ago with nothing logged since,
# must not read as healthy just because no error line has appeared yet.
_CONNECTION_SUCCESS_MARKERS = (
    "SMS sent on device",
    "Written message",
    "Received message",
)
# Weaker evidence than an actual send/receive: a routine status poll (SMS
# memory status, network name) that succeeded cleanly. A modem that has
# never had a message to send/receive -- freshly fixed, or just idle --
# would otherwise never accumulate a _CONNECTION_SUCCESS_MARKERS line and
# could never be marked reachable, even though it's working fine; this
# would also permanently block it from ever being handed a job to prove
# itself, since the API only dispatches to modems already marked online.
_CONNECTION_HEALTHY_POLL_MARKERS = (
    "SMS status received",
    "Network name received",
    # Older Wavecom firmware can reject Gammu's SMS-memory status query
    # with UNKNOWN[27] even while AT commands, network registration, and
    # outbound SMS all work. The response still proves that the modem is
    # connected and answering; fatal serial/init errors remain authoritative
    # because the newest matching log line wins below.
    "Error getting SMS status: Unknown error. (UNKNOWN[27])",
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
        modem_port: str | None = None,
        smsd_log_stale_after_seconds: int = 120,
    ) -> None:
        self.outbox_path = Path(outbox_path)
        self.sent_path = Path(sent_path)
        self.error_path = Path(error_path)
        self.inbox_path = Path(inbox_path)
        for path in (self.outbox_path, self.sent_path, self.error_path, self.inbox_path):
            path.mkdir(parents=True, exist_ok=True)

        self.smsd_log_path = Path(smsd_log_path) if smsd_log_path else None
        self.modem_port = modem_port
        self.smsd_log_stale_after_seconds = smsd_log_stale_after_seconds

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
        # The FILES backend uses the extension's `d` flag to request a
        # carrier delivery report. `DeliveryReport = log` only controls how
        # SMSD handles a report after it arrives; it does not request one.
        filename = (
            f"{_OUT_PREFIX}A{now:%Y%m%d_%H%M%S}_{now.microsecond:06d}_"
            f"{safe_phone}_{queue_id}.txtd"
        )
        target = self.outbox_path / filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(message_body, encoding="utf-8")
        temporary.replace(target)

    def fetch_delivery_updates(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for entry in sorted(self.sent_path.glob(f"{_OUT_PREFIX}*.txt*")):
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

        for entry in sorted(self.error_path.glob(f"{_OUT_PREFIX}*.txt*")):
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
        # OUT<priority><date>_<time>_<serial>_<recipient>_<note>.txt[d]
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

    def _configured_serial_port_present(self) -> bool | None:
        """Return whether the configured serial device exists, when the OS
        offers a safe read-only way to check without opening SMSD's port."""
        if not self.modem_port:
            return None

        expected = self.modem_port.rstrip(":").upper()
        if os.name == "nt":
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DEVICEMAP\SERIALCOMM",
                ) as key:
                    index = 0
                    ports: set[str] = set()
                    while True:
                        try:
                            _, value, _ = winreg.EnumValue(key, index)
                        except OSError:
                            break
                        ports.add(str(value).rstrip(":").upper())
                        index += 1
                return expected in ports
            except OSError:
                return False

        if self.modem_port.startswith("/"):
            return Path(self.modem_port).exists()
        return None

    def is_modem_reachable(self, *, tail_bytes: int = 8192) -> bool:
        """Infer modem connectivity from gammu-smsd's own log instead of
        probing the port ourselves -- gammu-smsd holds the COM port
        exclusively while running, so a second process trying to open it
        (e.g. `gammu identify`) always fails with "already opened by
        another app" regardless of whether the modem itself is reachable.

        Finds whichever came last in the log tail: a fatal connection error,
        or evidence the modem answered (an actual send/receive, or a clean
        status/network poll). Whichever is more recent wins. This is
        deliberately NOT anchored to only the lines after the latest
        "Starting phone communication..." marker: SMSD reconnects
        periodically even while healthy, and if the agent's periodic check
        happens to sample the log right as a fresh reconnect attempt is
        logged but before its outcome is, anchoring to "since last attempt"
        would see no evidence yet and wrongly report unreachable -- even
        though the previous cycle just proved the modem fine. Only an
        actual error occurring after the last known-good evidence should
        flip this to unreachable.

        Absence of any evidence at all (never attempted, or nothing logged
        since a stale mark) is not enough to call it healthy -- a stuck,
        endlessly retrying SMSD, or one just restarted, must not read as
        healthy by default. A configured but missing log is unhealthy. A
        stale log is also unhealthy unless Windows still confirms the
        configured serial port exists and the last logged modem outcome was
        healthy. Some older Wavecom modems do not emit periodic log entries
        after answering SMSD's initial status query, so log age alone cannot
        be treated as a disconnect for those devices.

        The registry-based port check is used only as a fast-fail: for USB
        serial adapters, Windows can leave the port listed in SERIALCOMM for
        a while after the device is unplugged or powered off, so a `True`/`None`
        result here is not trusted as proof of reachability -- only an
        explicit `False` short-circuits."""
        port_present = self._configured_serial_port_present()
        if port_present is False:
            return False

        if not self.smsd_log_path:
            return True
        if not self.smsd_log_path.exists():
            return False

        try:
            log_is_stale = (
                self.smsd_log_stale_after_seconds > 0
                and time.time() - self.smsd_log_path.stat().st_mtime > self.smsd_log_stale_after_seconds
            )
            if log_is_stale and port_present is not True:
                return False
            with self.smsd_log_path.open("rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - tail_bytes))
                tail = handle.read().decode("utf-8", errors="replace")
        except OSError:
            return False

        lines = tail.splitlines()
        last_good_index = None
        for index, line in enumerate(lines):
            if any(marker in line for marker in _CONNECTION_SUCCESS_MARKERS) or any(
                marker in line for marker in _CONNECTION_HEALTHY_POLL_MARKERS
            ):
                last_good_index = index

        last_error_index = None
        for index, line in enumerate(lines):
            if any(marker in line for marker in _CONNECTION_ERROR_MARKERS):
                last_error_index = index

        if last_good_index is None:
            return False
        if last_error_index is None:
            return True
        return last_good_index > last_error_index

    def simulate_send_once(self, *, limit: int = 50) -> int:
        """
        Development helper: move queued outbox files straight to sent/ without a
        real modem. Keep disabled in production where Gammu SMSD handles send.
        """
        processed = 0
        for entry in sorted(self.outbox_path.glob(f"{_OUT_PREFIX}*.txt*"))[:limit]:
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
