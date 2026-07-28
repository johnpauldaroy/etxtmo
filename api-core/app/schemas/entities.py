from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import CampaignStatus, ModemStatus, QueueStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str
    is_superuser: bool = False
    branch_id: uuid.UUID | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str
    is_active: bool
    is_superuser: bool


class BranchCreate(BaseModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=255)
    timezone: str = "Asia/Manila"


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    timezone: str
    is_active: bool


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


class UserBranchAssign(BaseModel):
    user_id: uuid.UUID
    branch_id: uuid.UUID
    role_id: int | None = None


class ContactCreate(BaseModel):
    branch_id: uuid.UUID
    phone_number: str
    first_name: str | None = None
    last_name: str | None = None
    metadata_json: dict[str, Any] | None = None
    consented: bool = True


class ContactUpdate(BaseModel):
    phone_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    metadata_json: dict[str, Any] | None = None
    consented: bool | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    phone_number: str
    first_name: str | None
    last_name: str | None
    consented: bool
    opted_out_at: datetime | None
    deleted_at: datetime | None


class ContactGroupCreate(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ContactGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    description: str | None
    member_count: int = 0
    eligible_member_count: int = 0
    created_at: datetime
    deleted_at: datetime | None


class GroupMemberAdd(BaseModel):
    contact_id: uuid.UUID


class GroupMembersReplace(BaseModel):
    contact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)


class ContactGroupDetailOut(ContactGroupOut):
    members: list[ContactOut] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    branch_id: uuid.UUID
    name: str
    body: str
    is_official: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    is_official: bool | None = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    body: str
    is_official: bool
    deleted_at: datetime | None


class CampaignCreate(BaseModel):
    branch_id: uuid.UUID
    name: str
    template_id: uuid.UUID | None = None
    message_body: str | None = None
    group_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None
    timezone: str | None = None
    metadata_json: dict[str, Any] | None = None


class CampaignBatchRow(BaseModel):
    phone_number: str
    message_body: str


class CampaignBatchUpload(BaseModel):
    branch_id: uuid.UUID
    name: str | None = None
    timezone: str | None = None
    rows: list[CampaignBatchRow]


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    status: CampaignStatus
    scheduled_at: datetime | None
    timezone: str
    created_at: datetime


class CampaignStatusUpdate(BaseModel):
    status: CampaignStatus


def normalize_days_of_week(value: str) -> str:
    try:
        days = {int(part.strip()) for part in value.split(",") if part.strip()}
    except ValueError as exc:
        raise ValueError("days_of_week must be comma-separated numbers from 0 (Sunday) to 6 (Saturday)") from exc
    if not days or any(day < 0 or day > 6 for day in days):
        raise ValueError("days_of_week must contain at least one day from 0 (Sunday) to 6 (Saturday)")
    return ",".join(str(day) for day in sorted(days))


def validate_iana_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("timezone must be a valid IANA timezone, such as Asia/Manila") from exc
    return value


class RuleCreate(BaseModel):
    branch_id: uuid.UUID
    name: str
    minute_of_day: int = Field(ge=0, le=1439)
    days_of_week: str = "0,1,2,3,4,5,6"
    timezone: str
    group_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    message_body: str | None = None
    filter_json: dict[str, Any] | None = None
    is_active: bool = True

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: str) -> str:
        return normalize_days_of_week(value)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return validate_iana_timezone(value)


class RuleUpdate(BaseModel):
    name: str | None = None
    minute_of_day: int | None = Field(default=None, ge=0, le=1439)
    days_of_week: str | None = None
    timezone: str | None = None
    group_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    message_body: str | None = None
    filter_json: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: str | None) -> str | None:
        return normalize_days_of_week(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        return validate_iana_timezone(value) if value is not None else None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    minute_of_day: int
    days_of_week: str
    timezone: str
    is_active: bool
    template_id: uuid.UUID | None
    message_body: str | None
    filter_json: dict[str, Any] | None


class QueueItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_recipient_id: uuid.UUID
    status: QueueStatus
    attempts: int
    max_attempts: int
    next_attempt_at: datetime
    external_message_id: str | None
    error_message: str | None
    modem_id: uuid.UUID | None = None
    execution_branch_id: uuid.UUID | None = None
    failover_route_id: uuid.UUID | None = None
    phone_number: str | None = None
    message_body: str | None = None
    campaign_name: str = ""
    sent_at: datetime | None = None


class IncomingMessageCreate(BaseModel):
    branch_id: uuid.UUID
    modem_id: uuid.UUID | None = None
    phone_number: str
    message_text: str
    received_at: datetime
    raw_payload: dict[str, Any] | None = None


class IncomingMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    modem_id: uuid.UUID | None
    phone_number: str
    contact_name: str | None = None
    message_text: str
    received_at: datetime
    processed: bool


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID | None
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    payload: dict[str, Any] | None
    created_at: datetime


class ModemRegister(BaseModel):
    branch_id: uuid.UUID
    node_name: str
    name: str
    imei: str | None = None
    port: str | None = None


class ModemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    node_name: str
    name: str
    imei: str | None
    port: str | None
    status: ModemStatus
    last_seen_at: datetime | None


class FailoverPolicyUpsert(BaseModel):
    branch_id: uuid.UUID
    enabled: bool = False
    offline_after_seconds: int = Field(default=90, ge=30, le=3600)
    failover_delay_seconds: int = Field(default=60, ge=0, le=86400)
    claim_timeout_seconds: int = Field(default=120, ge=30, le=3600)


class FailoverPolicyOut(FailoverPolicyUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None


class FailoverRouteCreate(BaseModel):
    source_branch_id: uuid.UUID
    backup_branch_id: uuid.UUID
    priority: int = Field(default=1, ge=1, le=100)
    enabled: bool = True


class FailoverRouteOut(FailoverRouteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    backup_branch_code: str | None = None
    backup_branch_name: str | None = None


class FailoverStatusOut(BaseModel):
    policy: FailoverPolicyOut
    routes: list[FailoverRouteOut]
    local_modems_healthy: bool
    healthy_local_modems: int
    failover_active: bool
    pending_messages: int
    failover_messages: int


class SimCardCreate(BaseModel):
    branch_id: uuid.UUID
    modem_id: uuid.UUID | None = None
    msisdn: str
    network_name: str | None = None
    is_active: bool = True


class SimCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    modem_id: uuid.UUID | None
    msisdn: str
    network_name: str | None
    is_active: bool


class HeartbeatRequest(BaseModel):
    branch_id: uuid.UUID
    node_name: str
    status: str
    payload: dict[str, Any] | None = None


class QueuePullRequest(BaseModel):
    branch_id: uuid.UUID
    modem_id: uuid.UUID | None = None
    limit: int = Field(default=50, ge=1, le=500)


class QueueResultItem(BaseModel):
    queue_id: uuid.UUID
    status: QueueStatus
    external_message_id: str | None = None
    error_message: str | None = None


class QueueResultRequest(BaseModel):
    branch_id: uuid.UUID
    modem_id: uuid.UUID
    node_name: str
    items: list[QueueResultItem]


class NodeEventRequest(BaseModel):
    branch_id: uuid.UUID
    node_name: str
    event_type: str
    payload: dict[str, Any] | None = None


class ReportSummary(BaseModel):
    branch_id: uuid.UUID | None = None
    campaigns_total: int
    messages_sent: int
    messages_failed: int
    pending_queue: int


class ApiKeyCreate(BaseModel):
    branch_id: uuid.UUID
    label: str = Field(max_length=120)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    label: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    api_key: str


class SmsSendRequest(BaseModel):
    to: str = Field(min_length=5, max_length=32)
    message: str = Field(min_length=1, max_length=1600)


class SmsSendResponse(BaseModel):
    message_id: uuid.UUID
    status: str
    to: str


class SmsStatusResponse(BaseModel):
    message_id: uuid.UUID
    status: str
    to: str
    attempts: int
    error_message: str | None
    sent_at: datetime | None
