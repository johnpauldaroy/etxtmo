from __future__ import annotations

import uuid

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")
    api_username: str = Field(default="branch-agent", alias="API_USERNAME")
    api_password: str = Field(default="change-me", alias="API_PASSWORD")
    branch_id: uuid.UUID = Field(alias="BRANCH_ID")
    node_name: str = Field(default="branch-node-01", alias="NODE_NAME")
    modem_name: str = Field(default="modem-1", alias="MODEM_NAME")
    modem_imei: str | None = Field(default=None, alias="MODEM_IMEI")
    modem_port: str | None = Field(default=None, alias="MODEM_PORT")
    poll_interval_seconds: int = Field(default=10, alias="POLL_INTERVAL_SECONDS")
    heartbeat_interval_seconds: int = Field(default=30, alias="HEARTBEAT_INTERVAL_SECONDS")
    gammu_outbox_path: str = Field(default="./gammu-spool/outbox", alias="GAMMU_OUTBOX_PATH")
    gammu_sent_path: str = Field(default="./gammu-spool/sent", alias="GAMMU_SENT_PATH")
    gammu_error_path: str = Field(default="./gammu-spool/error", alias="GAMMU_ERROR_PATH")
    gammu_inbox_path: str = Field(default="./gammu-spool/inbox", alias="GAMMU_INBOX_PATH")
    gammu_cursor_db_path: str = Field(default="./gammu-cursor.sqlite", alias="GAMMU_CURSOR_DB_PATH")
    simulate_send: bool = Field(default=False, alias="SIMULATE_SEND")
    simulate_send_batch_size: int = Field(default=50, alias="SIMULATE_SEND_BATCH_SIZE")
    gammu_exe_path: str | None = Field(default=None, alias="GAMMU_EXE_PATH")
    gammu_config_path: str | None = Field(default=None, alias="GAMMU_CONFIG_PATH")
    modem_check_interval_seconds: int = Field(default=60, alias="MODEM_CHECK_INTERVAL_SECONDS")
