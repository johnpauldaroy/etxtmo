"""Diagnose why this branch's modem is reporting unhealthy.

Run on the BRANCH PC (the one with the modem), from the branch-agent folder:

    python diagnose.py

Read-only: opens no serial port, sends no SMS, changes no config. Safe to run
while the agent and gammu-smsd are running -- and it must be, since SMSD holds
the COM port exclusively and anything that opened it would break sending.

Reports the modem status the agent WOULD send on its next heartbeat, and why.
Where possible it calls the agent's own is_modem_reachable() rather than
reimplementing the rule, so the two cannot disagree.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OK = "  [OK]  "
BAD = "  [BAD] "
WARN = "  [??]  "
INFO = "        "


def heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def main() -> int:
    print("e-txtmo branch agent diagnostics")
    print(f"run at {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(f"folder {HERE}")

    problems: list[str] = []
    notes: list[str] = []

    # ------------------------------------------------------------------
    heading("1. Agent configuration")

    env_path = HERE / ".env"
    if not env_path.exists():
        print(f"{BAD}no .env found at {env_path}")
        print(f"{INFO}The agent cannot start without it. Nothing else can be checked.")
        return 1
    print(f"{OK}.env found")

    try:
        from agent.config import AgentSettings

        settings = AgentSettings(_env_file=str(env_path))
    except Exception as exc:  # noqa: BLE001
        print(f"{BAD}could not load settings: {exc}")
        print(f"{INFO}Fix .env before continuing; the agent would fail the same way.")
        return 1

    print(f"{INFO}branch_id   {settings.branch_id}")
    print(f"{INFO}node_name   {settings.node_name}")
    print(f"{INFO}modem_name  {settings.modem_name}")
    print(f"{INFO}modem_port  {settings.modem_port or '(not set)'}")
    print(f"{INFO}api_base    {settings.api_base_url}")
    print(f"{INFO}smsd_log    {settings.smsd_log_path or '(not set)'}")

    if settings.simulate_send:
        print(f"{WARN}SIMULATE_SEND is true -- messages are marked sent WITHOUT a real modem")
        notes.append("SIMULATE_SEND=true: sending is faked. Set it false for production.")

    # ------------------------------------------------------------------
    heading("2. Serial port")

    if not settings.modem_port:
        print(f"{WARN}MODEM_PORT not set, so the port check is skipped")
        print(f"{INFO}The agent treats 'unknown' as not-a-failure, so this alone")
        print(f"{INFO}will not mark the modem unhealthy.")
    else:
        present = _port_present(settings.modem_port)
        if present is False:
            print(f"{BAD}{settings.modem_port} is NOT present on this machine")
            print(f"{INFO}This alone forces the modem unreachable.")
            problems.append(
                f"{settings.modem_port} does not exist. The modem is unplugged/powered off, "
                f"or Windows assigned it a different COM port after a reboot. "
                f"Check Device Manager > Ports, then set MODEM_PORT in .env to match.",
            )
            _list_windows_ports()
        elif present is True:
            print(f"{OK}{settings.modem_port} is present")
            print(f"{INFO}Note: Windows can keep a USB port listed briefly after unplug,")
            print(f"{INFO}so this is not by itself proof the modem is answering.")
        else:
            print(f"{WARN}cannot verify {settings.modem_port} on this OS; skipped")

    # ------------------------------------------------------------------
    heading("3. Gammu SMSD log")

    log_path = Path(settings.smsd_log_path) if settings.smsd_log_path else None
    if log_path is None:
        print(f"{WARN}SMSD_LOG_PATH not set")
        print(f"{INFO}With no log configured the agent assumes the modem is fine,")
        print(f"{INFO}so it cannot be the cause of an 'error' status.")
    elif not log_path.exists():
        print(f"{BAD}log file does not exist: {log_path}")
        problems.append(
            f"SMSD log missing at {log_path}. Either gammu-smsd has never run, or "
            f"SMSD_LOG_PATH points somewhere wrong. A configured-but-missing log is "
            f"treated as unhealthy.",
        )
    else:
        age = time.time() - log_path.stat().st_mtime
        stale_after = settings.smsd_log_stale_after_seconds
        print(f"{INFO}path  {log_path}")
        print(f"{INFO}size  {log_path.stat().st_size:,} bytes")
        print(f"{INFO}age   {age:,.0f}s (stale threshold {stale_after}s)")

        if stale_after > 0 and age > stale_after:
            print(f"{BAD}log has not been written for {age:,.0f}s")
            problems.append(
                f"SMSD log is stale ({age:,.0f}s old). gammu-smsd is probably stopped "
                f"or wedged. Restart the gammu-smsd service and watch the log update.",
            )
        else:
            print(f"{OK}log is being written recently")

        _show_log_evidence(log_path)

    # ------------------------------------------------------------------
    heading("4. The agent's own verdict")

    verdict = _agent_verdict(settings)
    if verdict is None:
        print(f"{WARN}could not evaluate (agent modules not importable here)")
    elif verdict:
        print(f"{OK}is_modem_reachable() -> True")
        print(f"{INFO}The next heartbeat would report 'online'.")
        print(f"{INFO}If the dashboard still shows error, the agent process is not")
        print(f"{INFO}running -- see section 5.")
    else:
        print(f"{BAD}is_modem_reachable() -> False")
        print(f"{INFO}The next heartbeat reports 'offline', which the API stores as")
        print(f"{INFO}status 'error'. That is exactly what the dashboard shows.")

    # ------------------------------------------------------------------
    heading("5. Agent process")

    print(f"{INFO}This script cannot tell whether the agent service is running.")
    print(f"{INFO}Check it directly:")
    print(f"{INFO}    sc query TextKonekBranchAgent-001")
    print(f"{INFO}    sc query GammuSMSD-001")
    print(f"{INFO}    or Task Manager > Details > python.exe")
    print(f"{INFO}If last_seen_at on the dashboard is recent, it IS running --")
    print(f"{INFO}only a heartbeat updates that timestamp.")

    # ------------------------------------------------------------------
    heading("6. Spool folders")

    for label, raw in (
        ("outbox", settings.gammu_outbox_path),
        ("sent", settings.gammu_sent_path),
        ("error", settings.gammu_error_path),
        ("inbox", settings.gammu_inbox_path),
    ):
        path = Path(raw)
        if not path.exists():
            print(f"{WARN}{label:6} missing: {path}")
            continue
        count = len(list(path.glob("*")))
        marker = OK
        if label == "outbox" and count > 0:
            marker = WARN
        if label == "error" and count > 0:
            marker = WARN
        print(f"{marker}{label:6} {count:>5} file(s)  {path}")

    outbox_count = _safe_count(settings.gammu_outbox_path)
    error_count = _safe_count(settings.gammu_error_path)
    if outbox_count:
        notes.append(
            f"{outbox_count} file(s) waiting in outbox -- gammu-smsd has not picked "
            f"them up, consistent with SMSD being stopped.",
        )
    if error_count:
        notes.append(f"{error_count} file(s) in the error folder -- sends that failed at the modem.")

    # ------------------------------------------------------------------
    heading("Summary")

    if not problems:
        print("No blocking problem found by this script.")
        print("If the dashboard still shows 'error', the most likely remaining causes")
        print("are that the agent process is not running, or it is pointed at a")
        print("different branch/node than the one you are looking at.")
    else:
        print(f"{len(problems)} likely cause(s), most specific first:\n")
        for index, problem in enumerate(problems, start=1):
            print(f"  {index}. {problem}\n")

    if notes:
        print("Also worth knowing:\n")
        for note in notes:
            print(f"  - {note}")

    return 1 if problems else 0


def _safe_count(raw: str) -> int:
    path = Path(raw)
    return len(list(path.glob("*"))) if path.exists() else 0


def _port_present(modem_port: str) -> bool | None:
    """Mirror of GammuBackend._configured_serial_port_present, without needing
    a full backend instance (which would create spool folders)."""
    expected = modem_port.rstrip(":").upper()
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
                ports: set[str] = set()
                index = 0
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
    if modem_port.startswith("/"):
        return Path(modem_port).exists()
    return None


def _list_windows_ports() -> None:
    if os.name != "nt":
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            found = []
            index = 0
            while True:
                try:
                    _, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                found.append(str(value))
                index += 1
        if found:
            print(f"{INFO}ports Windows currently reports: {', '.join(sorted(found))}")
        else:
            print(f"{INFO}Windows reports no serial ports at all -- modem not connected.")
    except OSError:
        pass


def _show_log_evidence(log_path: Path, tail_bytes: int = 8192) -> None:
    """Show the newest healthy and error markers, the same ones the agent
    weighs against each other."""
    try:
        from agent.gammu_backend import (
            _CONNECTION_ERROR_MARKERS,
            _CONNECTION_HEALTHY_POLL_MARKERS,
            _CONNECTION_SUCCESS_MARKERS,
        )
    except Exception:  # noqa: BLE001
        return

    try:
        with log_path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - tail_bytes))
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:
        print(f"{BAD}cannot read log: {exc}")
        return

    lines = tail.splitlines()
    good = [(i, l) for i, l in enumerate(lines) if _matches(l, _CONNECTION_SUCCESS_MARKERS + _CONNECTION_HEALTHY_POLL_MARKERS)]
    bad = [(i, l) for i, l in enumerate(lines) if _matches(l, _CONNECTION_ERROR_MARKERS)]

    print()
    if good:
        print(f"{INFO}newest 'modem answered' line:")
        print(f"{INFO}  {good[-1][1].strip()[:150]}")
    else:
        print(f"{INFO}no evidence the modem ever answered in the last {tail_bytes} bytes")

    if bad:
        print(f"{INFO}newest connection-error line:")
        print(f"{INFO}  {bad[-1][1].strip()[:150]}")
    else:
        print(f"{INFO}no connection-error lines in the tail")

    if good and bad:
        winner = "healthy" if good[-1][0] > bad[-1][0] else "ERROR"
        print(f"{INFO}whichever is newer wins -> {winner}")

    print()
    print(f"{INFO}last 8 log lines:")
    for line in lines[-8:]:
        print(f"{INFO}  | {line.strip()[:150]}")


def _matches(line: str, markers: tuple[str, ...]) -> bool:
    return any(marker in line for marker in markers)


def _agent_verdict(settings) -> bool | None:  # noqa: ANN001
    """Call the agent's real reachability check, so this script and the agent
    can never disagree."""
    try:
        from agent.gammu_backend import GammuBackend
    except Exception:  # noqa: BLE001
        return None

    try:
        backend = GammuBackend(
            outbox_path=settings.gammu_outbox_path,
            sent_path=settings.gammu_sent_path,
            error_path=settings.gammu_error_path,
            inbox_path=settings.gammu_inbox_path,
            cursor_db_path=settings.gammu_cursor_db_path,
            smsd_log_path=settings.smsd_log_path,
            modem_port=settings.modem_port,
            smsd_log_stale_after_seconds=settings.smsd_log_stale_after_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"{WARN}could not open backend: {exc}")
        return None

    try:
        return backend.is_modem_reachable()
    finally:
        backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
