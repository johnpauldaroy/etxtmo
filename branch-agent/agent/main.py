from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from agent.api_client import ApiClient
from agent.config import AgentSettings
from agent.gammu_backend import GammuBackend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("branch-agent")


class BranchAgent:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.api = ApiClient(settings.api_base_url, settings.api_username, settings.api_password)
        self.backend = GammuBackend(
            outbox_path=settings.gammu_outbox_path,
            sent_path=settings.gammu_sent_path,
            error_path=settings.gammu_error_path,
            inbox_path=settings.gammu_inbox_path,
            cursor_db_path=settings.gammu_cursor_db_path,
        )
        self.modem_id: str | None = None
        self._last_heartbeat = 0.0

    def close(self) -> None:
        self.api.close()
        self.backend.close()

    def bootstrap(self) -> None:
        self.api.authenticate()
        modem = self.api.register_modem(
            {
                "branch_id": str(self.settings.branch_id),
                "node_name": self.settings.node_name,
                "name": self.settings.modem_name,
                "imei": self.settings.modem_imei,
                "port": self.settings.modem_port,
            },
        )
        self.modem_id = modem["id"]
        logger.info("Registered modem %s", self.modem_id)

    def heartbeat_if_due(self) -> None:
        now = time.time()
        if now - self._last_heartbeat < self.settings.heartbeat_interval_seconds:
            return
        self.api.heartbeat(
            {
                "branch_id": str(self.settings.branch_id),
                "node_name": self.settings.node_name,
                "status": "online",
                "payload": {"modem_id": self.modem_id, "timestamp": datetime.now(timezone.utc).isoformat()},
            },
        )
        self._last_heartbeat = now

    def push_results(self) -> None:
        updates = self.backend.fetch_delivery_updates()
        if not updates:
            return
        payload = {
            "branch_id": str(self.settings.branch_id),
            "modem_id": self.modem_id,
            "node_name": self.settings.node_name,
            "items": updates,
        }
        response = self.api.push_results(payload)
        logger.info("Synced results sent=%s failed=%s", response.get("sent"), response.get("failed"))

    def push_incoming(self) -> None:
        inbound_messages = self.backend.fetch_incoming_messages()
        for inbound in inbound_messages:
            self.api.push_incoming(
                {
                    "branch_id": str(self.settings.branch_id),
                    "modem_id": self.modem_id,
                    "phone_number": inbound["phone_number"],
                    "message_text": inbound["message_text"],
                    "received_at": inbound["received_at"],
                    "raw_payload": inbound["raw_payload"],
                },
            )
        if inbound_messages:
            logger.info("Synced inbound count=%s", len(inbound_messages))

    def pull_and_enqueue_jobs(self) -> None:
        jobs = self.api.pull_jobs(
            {
                "branch_id": str(self.settings.branch_id),
                "modem_id": self.modem_id,
                "limit": 100,
            },
        )
        if not jobs:
            return

        valid_jobs: list[dict[str, str]] = []
        invalid_results: list[dict[str, str | None]] = []
        for job in jobs:
            queue_id = job["id"]
            phone = job.get("phone_number")
            body = job.get("message_body")
            if not phone or not body:
                invalid_results.append(
                    {
                        "queue_id": queue_id,
                        "status": "failed",
                        "external_message_id": None,
                        "error_message": "Missing phone_number or message_body",
                    },
                )
                continue
            valid_jobs.append({"queue_id": queue_id, "phone": phone, "body": body})

        for job in valid_jobs:
            self.backend.enqueue_outbound(queue_id=job["queue_id"], phone_number=job["phone"], message_body=job["body"])
        logger.info("Queued outbound messages=%s", len(valid_jobs))

        if invalid_results:
            self.api.push_results(
                {
                    "branch_id": str(self.settings.branch_id),
                    "modem_id": self.modem_id,
                    "node_name": self.settings.node_name,
                    "items": invalid_results,
                },
            )

    def process_outbound_if_enabled(self) -> None:
        if not self.settings.simulate_send:
            return
        processed = self.backend.simulate_send_once(limit=self.settings.simulate_send_batch_size)
        if processed:
            logger.info("Simulated modem sends=%s", processed)

    def run_forever(self) -> None:
        self.bootstrap()
        if self.settings.simulate_send:
            logger.warning(
                "SIMULATE_SEND is enabled. Outbox messages will be marked sent locally "
                "without real modem delivery.",
            )
        while True:
            try:
                self.heartbeat_if_due()
                self.pull_and_enqueue_jobs()
                self.process_outbound_if_enabled()
                self.push_results()
                self.push_incoming()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    logger.warning("Auth expired, re-authenticating")
                    self.api.authenticate()
                else:
                    logger.exception("API status error")
                    self.api.send_error_event(str(self.settings.branch_id), self.settings.node_name, exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Agent loop error")
                try:
                    self.api.send_error_event(str(self.settings.branch_id), self.settings.node_name, exc)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to report agent error")
            time.sleep(self.settings.poll_interval_seconds)


def main() -> None:
    settings = AgentSettings()
    agent = BranchAgent(settings)
    try:
        agent.run_forever()
    finally:
        agent.close()


if __name__ == "__main__":
    main()
