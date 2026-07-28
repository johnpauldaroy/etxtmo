from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: str | None = None
        self._http = httpx.Client(timeout=30)

    def close(self) -> None:
        self._http.close()

    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            self.authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    def authenticate(self) -> None:
        response = self._http.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]

    def register_modem(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(
            f"{self.base_url}/api/node/register-modem",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return response.json()

    def heartbeat(self, payload: dict[str, Any]) -> None:
        response = self._http.post(
            f"{self.base_url}/api/node/heartbeat",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()

    def pull_jobs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._http.post(
            f"{self.base_url}/api/node/pull-jobs",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return response.json()

    def push_results(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(
            f"{self.base_url}/api/node/queue-results",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return response.json()

    def push_incoming(self, payload: dict[str, Any]) -> None:
        response = self._http.post(
            f"{self.base_url}/api/node/incoming",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()

    def push_event(self, payload: dict[str, Any]) -> None:
        response = self._http.post(
            f"{self.base_url}/api/node/event",
            json=payload,
            headers=self._auth_headers(),
        )
        response.raise_for_status()

    def send_error_event(self, branch_id: str, node_name: str, exc: Exception) -> None:
        self.push_event(
            {
                "branch_id": branch_id,
                "node_name": node_name,
                "event_type": "agent_error",
                "payload": {"error": str(exc), "timestamp": datetime.now(timezone.utc).isoformat()},
            },
        )

