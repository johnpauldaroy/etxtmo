from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import (
    ApiKey,
    Campaign,
    Contact,
    ContactGroup,
    CampaignStatus,
    CampaignRecipient,
    MessageLog,
    MessageQueue,
    Modem,
    OptOut,
    Template,
    User,
)
from app.schemas import CampaignBatchUpload, CampaignCreate, CampaignOut
from app.services.audit import record_audit_event
from app.services.campaigns import move_to_submission_state
from app.services.queue import expand_recipients_for_campaign, now_utc, queue_campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
MAX_BATCH_ROWS = 10_000


def _api_key_id_from_campaign(campaign: Campaign) -> uuid.UUID | None:
    metadata = campaign.metadata_json or {}
    if metadata.get("source") != "sms_gateway_api" or not metadata.get("api_key_id"):
        return None
    try:
        return uuid.UUID(str(metadata["api_key_id"]))
    except (TypeError, ValueError):
        return None


def _campaign_out(campaign: Campaign, api_key_labels: dict[uuid.UUID, str] | None = None) -> CampaignOut:
    metadata = campaign.metadata_json or {}
    api_key_id = _api_key_id_from_campaign(campaign)
    label = metadata.get("api_key_label")
    if api_key_id and api_key_labels and api_key_id in api_key_labels:
        label = api_key_labels[api_key_id]
    return CampaignOut.model_validate(campaign).model_copy(
        update={
            "source": metadata.get("source"),
            "api_key_id": api_key_id,
            "api_key_label": str(label) if label else None,
        },
    )


@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CampaignOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = list(db.execute(
        select(Campaign).where(Campaign.branch_id == branch_id).order_by(Campaign.created_at.desc()),
    ).scalars())
    api_key_ids = {api_key_id for row in rows if (api_key_id := _api_key_id_from_campaign(row))}
    api_key_labels = dict(
        db.execute(select(ApiKey.id, ApiKey.label).where(ApiKey.id.in_(api_key_ids))).all(),
    ) if api_key_ids else {}
    return [_campaign_out(row, api_key_labels) for row in rows]


@router.get("/api-keys/{api_key_id}/recipients")
def list_api_key_recipients(
    api_key_id: uuid.UUID,
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    assert_branch_access(db, current_user, branch_id)
    campaigns = [
        campaign
        for campaign in db.execute(
            select(Campaign)
            .where(Campaign.branch_id == branch_id)
            .order_by(Campaign.created_at.desc()),
        ).scalars()
        if _api_key_id_from_campaign(campaign) == api_key_id
    ]
    if not campaigns:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No API messages found for this key")

    campaign_ids = [campaign.id for campaign in campaigns]
    campaign_created_at = {campaign.id: campaign.created_at for campaign in campaigns}
    rows = db.execute(
        select(CampaignRecipient, Contact, MessageQueue, Modem)
        .outerjoin(Contact, Contact.id == CampaignRecipient.contact_id)
        .outerjoin(MessageQueue, MessageQueue.campaign_recipient_id == CampaignRecipient.id)
        .outerjoin(Modem, Modem.id == MessageQueue.modem_id)
        .where(CampaignRecipient.campaign_id.in_(campaign_ids))
        .order_by(CampaignRecipient.created_at.desc()),
    ).all()
    queue_ids = [queue.id for _, _, queue, _ in rows if queue]
    sent_at_by_queue = dict(
        db.execute(
            select(MessageLog.queue_id, func.max(MessageLog.created_at))
            .where(MessageLog.queue_id.in_(queue_ids), MessageLog.event_status == "sent")
            .group_by(MessageLog.queue_id),
        ).all(),
    ) if queue_ids else {}

    api_key = db.get(ApiKey, api_key_id)
    snapshot_label = (campaigns[0].metadata_json or {}).get("api_key_label")
    return {
        "api_key_id": str(api_key_id),
        "api_key_label": api_key.label if api_key and api_key.branch_id == branch_id else snapshot_label,
        "items": [
            {
                "id": str(recipient.id),
                "campaign_id": str(recipient.campaign_id),
                "queue_id": str(queue.id) if queue else None,
                "contact_name": (
                    " ".join(part for part in ((contact.first_name or "").strip(), (contact.last_name or "").strip()) if part)
                    if contact
                    else ""
                ),
                "phone_number": recipient.phone_number,
                "message_body": recipient.message_body,
                "status": queue.status.value if queue else recipient.status.value,
                "attempts": queue.attempts if queue else 0,
                "modem_name": modem.name if modem else None,
                "created_at": campaign_created_at[recipient.campaign_id].isoformat(),
                "sent_at": sent_at_by_queue.get(queue.id).isoformat() if queue and sent_at_by_queue.get(queue.id) else None,
                "error_message": queue.error_message if queue else None,
            }
            for recipient, contact, queue, modem in rows
        ],
    }


@router.post("", response_model=CampaignOut)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CampaignOut:
    assert_branch_access(db, current_user, payload.branch_id)
    if payload.template_id:
        template = db.get(Template, payload.template_id)
        if template is None or template.deleted_at is not None or template.branch_id != payload.branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template is not available for this branch")
    if payload.group_id:
        group = db.get(ContactGroup, payload.group_id)
        if group is None or group.deleted_at is not None or group.branch_id != payload.branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact group is not available for this branch")
    campaign = Campaign(
        branch_id=payload.branch_id,
        name=payload.name,
        template_id=payload.template_id,
        status=CampaignStatus.draft,
        scheduled_at=payload.scheduled_at,
        timezone=payload.timezone or "Asia/Manila",
        created_by=current_user.id,
        metadata_json=(payload.metadata_json or {}) | {"group_id": str(payload.group_id) if payload.group_id else None},
    )
    db.add(campaign)
    db.flush()

    if payload.message_body:
        campaign.metadata_json = (campaign.metadata_json or {}) | {"message_body": payload.message_body}

    record_audit_event(
        db,
        action="campaign_created",
        entity_type="campaign",
        entity_id=str(campaign.id),
        user_id=current_user.id,
        branch_id=campaign.branch_id,
    )
    db.commit()
    db.refresh(campaign)
    return _campaign_out(campaign)


@router.post("/batch-upload")
def create_campaign_from_batch_upload(
    payload: CampaignBatchUpload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | int]:
    assert_branch_access(db, current_user, payload.branch_id)

    if not payload.rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch upload has no rows")
    if len(payload.rows) > MAX_BATCH_ROWS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch upload supports up to 10,000 rows")

    name = (payload.name or "").strip() or f"Batch Upload {now_utc().strftime('%Y-%m-%d %H:%M:%S')}"
    campaign = Campaign(
        branch_id=payload.branch_id,
        name=name,
        status=CampaignStatus.draft,
        timezone=payload.timezone or "Asia/Manila",
        created_by=current_user.id,
        metadata_json={"source": "batch_upload"},
    )
    db.add(campaign)
    db.flush()

    phones = {(row.phone_number or "").strip() for row in payload.rows}
    phones.discard("")
    contact_map: dict[str, Contact] = {}
    if phones:
        contacts = db.execute(
            select(Contact).where(
                Contact.branch_id == payload.branch_id,
                Contact.deleted_at.is_(None),
                Contact.phone_number.in_(phones),
            ),
        ).scalars()
        contact_map = {contact.phone_number: contact for contact in contacts}

    opted_out = set(
        db.execute(select(OptOut.phone_number).where(OptOut.branch_id == payload.branch_id)).scalars(),
    )

    inserted = 0
    skipped = 0
    seen_phones: set[str] = set()
    for row in payload.rows:
        phone_number = (row.phone_number or "").strip()
        message_body = (row.message_body or "").strip()
        if not phone_number or not message_body:
            skipped += 1
            continue
        if phone_number in seen_phones:
            skipped += 1
            continue
        if phone_number in opted_out:
            skipped += 1
            continue

        contact = contact_map.get(phone_number)
        if contact is not None and not contact.consented:
            skipped += 1
            continue

        db.add(
            CampaignRecipient(
                campaign_id=campaign.id,
                branch_id=payload.branch_id,
                contact_id=contact.id if contact else None,
                phone_number=phone_number,
                message_body=message_body,
            ),
        )
        seen_phones.add(phone_number)
        inserted += 1

    if inserted == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid rows found. Ensure each row has phone_number and message and is not opted out.",
        )

    db.flush()
    move_to_submission_state(db, campaign)
    queued = queue_campaign(db, campaign)
    campaign.status = CampaignStatus.queued if queued else CampaignStatus.failed

    record_audit_event(
        db,
        action="campaign_batch_uploaded",
        entity_type="campaign",
        entity_id=str(campaign.id),
        user_id=current_user.id,
        branch_id=campaign.branch_id,
        payload={
            "status": campaign.status.value,
            "inserted": inserted,
            "skipped": skipped,
            "queued": queued,
        },
    )
    db.commit()
    return {
        "campaign_id": str(campaign.id),
        "status": campaign.status.value,
        "inserted": inserted,
        "skipped": skipped,
        "queued": queued,
    }


@router.post("/{campaign_id}/submit")
def submit_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | int]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assert_branch_access(db, current_user, campaign.branch_id)
    if campaign.status not in {CampaignStatus.draft, CampaignStatus.failed}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign cannot be submitted from this state")

    metadata = campaign.metadata_json or {}
    group_id_value = metadata.get("group_id")
    message_body = metadata.get("message_body")
    group_id = uuid.UUID(group_id_value) if group_id_value else None
    try:
        recipients = expand_recipients_for_campaign(db, campaign, group_id=group_id, raw_message=message_body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if recipients == 0:
        campaign.status = CampaignStatus.failed
        db.flush()
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recipients found after filters")

    move_to_submission_state(db, campaign)
    queued = 0
    if campaign.scheduled_at and campaign.scheduled_at > datetime.now(timezone.utc):
        campaign.status = CampaignStatus.approved
    else:
        queued = queue_campaign(db, campaign)
        campaign.status = CampaignStatus.queued if queued else CampaignStatus.failed

    record_audit_event(
        db,
        action="campaign_submitted",
        entity_type="campaign",
        entity_id=str(campaign.id),
        user_id=current_user.id,
        branch_id=campaign.branch_id,
        payload={"next_state": campaign.status.value, "recipients": recipients, "queued": queued},
    )
    db.commit()
    return {"status": campaign.status.value, "recipients": recipients, "queued": queued}


@router.post("/{campaign_id}/queue")
def queue_campaign_now(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | int]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assert_branch_access(db, current_user, campaign.branch_id)
    if campaign.status not in {CampaignStatus.approved, CampaignStatus.failed, CampaignStatus.queued}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign not ready for queueing")
    count = queue_campaign(db, campaign)
    campaign.status = CampaignStatus.queued if count else CampaignStatus.failed
    db.flush()
    record_audit_event(
        db,
        action="campaign_queued",
        entity_type="campaign",
        entity_id=str(campaign.id),
        user_id=current_user.id,
        branch_id=campaign.branch_id,
        payload={"queued": count},
    )
    db.commit()
    return {"status": campaign.status.value, "queued": count}


@router.get("/{campaign_id}/recipients")
def list_campaign_recipients(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, object]]]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assert_branch_access(db, current_user, campaign.branch_id)
    rows = db.execute(
        select(CampaignRecipient, Contact, MessageQueue, Modem)
        .outerjoin(Contact, Contact.id == CampaignRecipient.contact_id)
        .outerjoin(MessageQueue, MessageQueue.campaign_recipient_id == CampaignRecipient.id)
        .outerjoin(Modem, Modem.id == MessageQueue.modem_id)
        .where(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.created_at.asc()),
    ).all()
    queue_ids = [queue.id for _, _, queue, _ in rows if queue]
    sent_at_by_queue = dict(
        db.execute(
            select(MessageLog.queue_id, func.max(MessageLog.created_at))
            .where(MessageLog.queue_id.in_(queue_ids), MessageLog.event_status == "sent")
            .group_by(MessageLog.queue_id),
        ).all(),
    ) if queue_ids else {}
    return {
        "items": [
            {
                "id": str(recipient.id),
                "queue_id": str(queue.id) if queue else None,
                "contact_name": (
                    " ".join(part for part in ((contact.first_name or "").strip(), (contact.last_name or "").strip()) if part)
                    if contact
                    else ""
                ),
                "phone_number": recipient.phone_number,
                "message_body": recipient.message_body,
                "status": queue.status.value if queue else recipient.status.value,
                "attempts": queue.attempts if queue else 0,
                "modem_name": modem.name if modem else None,
                "created_at": recipient.created_at.isoformat(),
                "sent_at": sent_at_by_queue.get(queue.id).isoformat() if queue and sent_at_by_queue.get(queue.id) else None,
                "error_message": queue.error_message if queue else None,
            }
            for recipient, contact, queue, modem in rows
        ],
    }
