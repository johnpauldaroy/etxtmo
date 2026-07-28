from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import Contact, IncomingMessage, OptOut, OptOutSource, User
from app.schemas import IncomingMessageCreate, IncomingMessageOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/incoming", tags=["incoming"])


def _phone_lookup_key(phone_number: str) -> str:
    digits = re.sub(r"\D", "", phone_number)
    if len(digits) == 11 and digits.startswith("09"):
        return f"63{digits[1:]}"
    if len(digits) == 12 and digits.startswith("639"):
        return digits
    return digits


@router.get("", response_model=list[IncomingMessageOut])
def list_incoming(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IncomingMessageOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(IncomingMessage).where(IncomingMessage.branch_id == branch_id).order_by(IncomingMessage.received_at.desc()).limit(500),
    ).scalars().all()
    contacts = db.execute(
        select(Contact).where(Contact.branch_id == branch_id, Contact.deleted_at.is_(None)),
    ).scalars().all()
    contact_names = {
        _phone_lookup_key(contact.phone_number): full_name
        for contact in contacts
        if (full_name := " ".join(part for part in (contact.first_name, contact.last_name) if part))
    }

    results: list[IncomingMessageOut] = []
    for row in rows:
        result = IncomingMessageOut.model_validate(row)
        result.contact_name = contact_names.get(_phone_lookup_key(row.phone_number))
        results.append(result)
    return results


@router.post("", response_model=IncomingMessageOut)
def create_incoming(
    payload: IncomingMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncomingMessageOut:
    assert_branch_access(db, current_user, payload.branch_id)
    item = IncomingMessage(**payload.model_dump(), processed=False)
    db.add(item)
    db.flush()

    message_text = payload.message_text.strip().upper()
    if message_text.startswith("STOP"):
        existing_optout = db.execute(
            select(OptOut).where(OptOut.branch_id == payload.branch_id, OptOut.phone_number == payload.phone_number),
        ).scalar_one_or_none()
        if existing_optout is None:
            db.add(
                OptOut(
                    branch_id=payload.branch_id,
                    phone_number=payload.phone_number,
                    source=OptOutSource.inbound,
                    reason="Inbound STOP",
                ),
            )
        contacts = db.execute(
            select(Contact).where(Contact.branch_id == payload.branch_id, Contact.phone_number == payload.phone_number),
        ).scalars()
        for contact in contacts:
            contact.opted_out_at = datetime.now(timezone.utc)
            contact.consented = False
        item.processed = True

    record_audit_event(
        db,
        action="incoming_message_received",
        entity_type="incoming_message",
        entity_id=str(item.id),
        user_id=current_user.id,
        branch_id=item.branch_id,
        payload={"phone_number": item.phone_number},
    )
    db.commit()
    db.refresh(item)
    return IncomingMessageOut.model_validate(item)
