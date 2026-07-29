from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class QueueStatus(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class RecipientStatus(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    opted_out = "opted_out"
    skipped = "skipped"


class ModemStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    error = "error"


class ApprovalStatus(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"


class OptOutSource(str, enum.Enum):
    inbound = "inbound"
    manual = "manual"
    import_batch = "import_batch"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Manila", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UserBranch(Base):
    __tablename__ = "user_branches"
    __table_args__ = (UniqueConstraint("user_id", "branch_id", name="uq_user_branch"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    role_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("roles.id"), nullable=True)


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("branch_id", "phone_number", name="uq_contact_branch_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    consented: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ContactGroup(Base, TimestampMixin):
    __tablename__ = "contact_groups"
    __table_args__ = (UniqueConstraint("branch_id", "name", name="uq_group_branch_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ContactGroupMember(Base):
    __tablename__ = "contact_group_members"
    __table_args__ = (UniqueConstraint("group_id", "contact_id", name="uq_group_contact"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("contact_groups.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("contacts.id"), nullable=False)


class Template(Base, TimestampMixin):
    __tablename__ = "templates"
    __table_args__ = (UniqueConstraint("branch_id", "name", name="uq_template_branch_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ScheduleRule(Base, TimestampMixin):
    __tablename__ = "schedule_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minute_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    days_of_week: Mapped[str] = mapped_column(String(30), default="0,1,2,3,4,5,6", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    group_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("contact_groups.id"), nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("templates.id"), nullable=True)
    message_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("templates.id"), nullable=True)
    schedule_rule_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("schedule_rules.id"), nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        default=CampaignStatus.draft,
        nullable=False,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CampaignRecipient(Base, TimestampMixin):
    __tablename__ = "campaign_recipients"
    __table_args__ = (UniqueConstraint("campaign_id", "phone_number", name="uq_campaign_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campaigns.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("contacts.id"), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus, name="recipient_status"),
        default=RecipientStatus.pending,
        nullable=False,
    )
    message_queue_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Modem(Base, TimestampMixin):
    __tablename__ = "modems"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    imei: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    port: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[ModemStatus] = mapped_column(
        Enum(ModemStatus, name="modem_status"),
        default=ModemStatus.offline,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class SimCard(Base, TimestampMixin):
    __tablename__ = "sim_cards"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    modem_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("modems.id"), nullable=True)
    msisdn: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    network_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FailoverPolicy(Base, TimestampMixin):
    __tablename__ = "failover_policies"
    __table_args__ = (UniqueConstraint("branch_id", name="uq_failover_policy_branch"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    offline_after_seconds: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    failover_delay_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    claim_timeout_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)


class FailoverRoute(Base, TimestampMixin):
    __tablename__ = "failover_routes"
    __table_args__ = (
        UniqueConstraint("source_branch_id", "backup_branch_id", name="uq_failover_route_branches"),
        Index("ix_failover_route_pick", "backup_branch_id", "enabled", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    backup_branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MessageQueue(Base, TimestampMixin):
    __tablename__ = "message_queue"
    __table_args__ = (
        Index("ix_message_queue_pick", "branch_id", "status", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campaigns.id"), nullable=False)
    campaign_recipient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campaign_recipients.id"), nullable=False)
    modem_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("modems.id"), nullable=True)
    execution_branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=True)
    failover_route_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("failover_routes.id"), nullable=True)
    # Superadmin manual override: when set, this branch's agents may claim the
    # item even though branch_id (true campaign ownership) points elsewhere,
    # bypassing the automatic failover-route/delay eligibility checks.
    forced_execution_branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=True)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, name="queue_status"),
        default=QueueStatus.pending,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("campaigns.id"), nullable=True, index=True)
    queue_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("message_queue.id"), nullable=True)
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_status: Mapped[str] = mapped_column(String(80), nullable=False)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)


class IncomingMessage(Base, TimestampMixin):
    __tablename__ = "incoming_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    modem_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("modems.id"), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ApprovalPolicy(Base, TimestampMixin):
    __tablename__ = "approval_policies"
    __table_args__ = (UniqueConstraint("branch_id", name="uq_approval_policy_branch"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_approvers: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CampaignApproval(Base):
    __tablename__ = "campaign_approvals"
    __table_args__ = (UniqueConstraint("campaign_id", "approver_user_id", name="uq_campaign_approver"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campaigns.id"), nullable=False, index=True)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, name="approval_status"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)


class ScheduleRuleRun(Base):
    __tablename__ = "schedule_rule_runs"
    __table_args__ = (UniqueConstraint("rule_id", "run_at", name="uq_schedule_rule_run"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("schedule_rules.id"), nullable=False, index=True)
    run_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("campaigns.id"), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class NodeHeartbeat(Base):
    __tablename__ = "node_heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class NodeSyncEvent(Base):
    __tablename__ = "node_sync_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)


class OptOut(Base):
    __tablename__ = "opt_outs"
    __table_args__ = (UniqueConstraint("branch_id", "phone_number", name="uq_optout_branch_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[OptOutSource] = mapped_column(Enum(OptOutSource, name="optout_source"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("branches.id"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)
