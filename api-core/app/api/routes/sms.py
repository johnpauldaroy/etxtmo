from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_api_key_context
from app.models import ApiKey, Branch, Campaign, CampaignRecipient, CampaignStatus, MessageLog, OptOut
from app.schemas import SmsSendRequest, SmsSendResponse, SmsStatusResponse
from app.services.audit import record_audit_event
from app.services.queue import queue_campaign

router = APIRouter(prefix="/v1/sms", tags=["sms-gateway"])


@router.post("/send", response_model=SmsSendResponse)
def send_sms(
    payload: SmsSendRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_context),
) -> SmsSendResponse:
    branch = db.get(Branch, api_key.branch_id)
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Branch unavailable")

    phone_number = payload.to.strip()
    opted_out = db.execute(
        select(OptOut.id).where(OptOut.branch_id == branch.id, OptOut.phone_number == phone_number),
    ).scalar_one_or_none()
    if opted_out:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Recipient has opted out")

    campaign = Campaign(
        branch_id=branch.id,
        name=f"API send to {phone_number}",
        status=CampaignStatus.approved,
        timezone=branch.timezone,
        metadata_json={"source": "sms_gateway_api", "api_key_id": str(api_key.id)},
    )
    db.add(campaign)
    db.flush()

    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        branch_id=branch.id,
        phone_number=phone_number,
        message_body=payload.message,
    )
    db.add(recipient)
    db.flush()

    queued = queue_campaign(db, campaign)
    campaign.status = CampaignStatus.queued if queued > 0 else CampaignStatus.failed

    record_audit_event(
        db,
        action="sms_gateway_send",
        entity_type="campaign",
        entity_id=str(campaign.id),
        branch_id=branch.id,
        payload={"api_key_id": str(api_key.id), "to": phone_number, "queued": queued},
    )
    db.commit()
    db.refresh(campaign)

    return SmsSendResponse(message_id=campaign.id, status=campaign.status.value, to=phone_number)


@router.get("/{message_id}/status", response_model=SmsStatusResponse)
def get_sms_status(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_context),
) -> SmsStatusResponse:
    campaign = db.get(Campaign, message_id)
    if campaign is None or campaign.branch_id != api_key.branch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    recipient = db.execute(
        select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id),
    ).scalar_one_or_none()
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    sent_log = db.execute(
        select(MessageLog)
        .where(
            MessageLog.campaign_id == campaign.id,
            MessageLog.event_type == "queue_result",
            MessageLog.event_status == "sent",
        )
        .order_by(MessageLog.created_at.desc()),
    ).scalars().first()

    error_log = db.execute(
        select(MessageLog)
        .where(
            MessageLog.campaign_id == campaign.id,
            MessageLog.event_type == "queue_result",
            MessageLog.event_status == "failed",
        )
        .order_by(MessageLog.created_at.desc()),
    ).scalars().first()

    attempts = 0
    error_message = None
    if error_log and error_log.details_json:
        attempts = error_log.details_json.get("attempts", 0)
        error_message = error_log.details_json.get("error_message")
    elif sent_log and sent_log.details_json:
        attempts = sent_log.details_json.get("attempts", 0)

    return SmsStatusResponse(
        message_id=campaign.id,
        status=recipient.status.value,
        to=recipient.phone_number,
        attempts=attempts,
        error_message=error_message,
        sent_at=sent_log.created_at if sent_log else None,
    )
