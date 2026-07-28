from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import Branch, Contact, ContactGroup, ContactGroupMember, OptOut, OptOutSource, User
from app.schemas import (
    ContactCreate,
    ContactUpdate,
    ContactGroupCreate,
    ContactGroupDetailOut,
    ContactGroupOut,
    ContactOut,
    GroupMemberAdd,
    GroupMembersReplace,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/contacts", tags=["contacts"])


class OptOutCreate(BaseModel):
    branch_id: uuid.UUID
    phone_number: str
    reason: str | None = None


@router.get("", response_model=list[ContactOut])
def list_contacts(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ContactOut]:
    assert_branch_access(db, current_user, branch_id)
    contacts = db.execute(
        select(Contact).where(Contact.branch_id == branch_id, Contact.deleted_at.is_(None)).order_by(Contact.created_at.desc()),
    ).scalars()
    return [ContactOut.model_validate(contact) for contact in contacts]


@router.post("", response_model=ContactOut)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactOut:
    assert_branch_access(db, current_user, payload.branch_id)
    existing = db.execute(
        select(Contact.id).where(Contact.branch_id == payload.branch_id, Contact.phone_number == payload.phone_number),
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact already exists for this branch")

    contact = Contact(**payload.model_dump())
    db.add(contact)
    db.flush()
    record_audit_event(
        db,
        action="contact_created",
        entity_type="contact",
        entity_id=str(contact.id),
        user_id=current_user.id,
        branch_id=contact.branch_id,
        payload={"phone_number": contact.phone_number},
    )
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactOut:
    contact = db.get(Contact, contact_id)
    if contact is None or contact.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    assert_branch_access(db, current_user, contact.branch_id)

    updates = payload.model_dump(exclude_unset=True)
    new_phone = updates.get("phone_number")
    if new_phone is not None:
        new_phone = new_phone.strip()
        if not new_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number is required")
        duplicate = db.execute(
            select(Contact.id).where(
                Contact.branch_id == contact.branch_id,
                Contact.phone_number == new_phone,
                Contact.id != contact.id,
            ),
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact already exists for this branch")
        updates["phone_number"] = new_phone

    for field, value in updates.items():
        setattr(contact, field, value)
    db.flush()
    record_audit_event(
        db,
        action="contact_updated",
        entity_type="contact",
        entity_id=str(contact.id),
        user_id=current_user.id,
        branch_id=contact.branch_id,
        payload={"updated_fields": sorted(updates)},
    )
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.delete("/{contact_id}")
def delete_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    assert_branch_access(db, current_user, contact.branch_id)
    contact.deleted_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db,
        action="contact_soft_deleted",
        entity_type="contact",
        entity_id=str(contact.id),
        user_id=current_user.id,
        branch_id=contact.branch_id,
    )
    db.commit()
    return {"status": "deleted"}


@router.post("/import-csv")
async def import_contacts_csv(
    branch_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    assert_branch_access(db, current_user, branch_id)

    raw = await file.read()
    stream = io.StringIO(raw.decode("utf-8"))
    reader = csv.DictReader(stream)

    inserted = 0
    skipped = 0
    known_phone_numbers = set(
        db.execute(
            select(Contact.phone_number).where(Contact.branch_id == branch_id),
        ).scalars(),
    )
    for row in reader:
        phone = (row.get("phone_number") or row.get("phone") or "").strip()
        if not phone:
            skipped += 1
            continue
        if phone in known_phone_numbers:
            skipped += 1
            continue
        contact = Contact(
            branch_id=branch_id,
            phone_number=phone,
            first_name=(row.get("first_name") or "").strip() or None,
            last_name=(row.get("last_name") or "").strip() or None,
            consented=(row.get("consented") or "true").strip().lower() in {"1", "true", "yes"},
        )
        db.add(contact)
        known_phone_numbers.add(phone)
        inserted += 1
    db.flush()
    record_audit_event(
        db,
        action="contacts_csv_imported",
        entity_type="contacts",
        user_id=current_user.id,
        branch_id=branch_id,
        payload={"inserted": inserted, "skipped": skipped, "file_name": file.filename},
    )
    db.commit()
    return {"inserted": inserted, "skipped": skipped}


@router.get("/export-csv")
def export_contacts_csv(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_branch_access(db, current_user, branch_id)
    contacts = db.execute(
        select(Contact).where(Contact.branch_id == branch_id, Contact.deleted_at.is_(None)).order_by(Contact.id.asc()),
    ).scalars()

    output = io.StringIO()
    writer = csv.writer(output)
    branch = db.get(Branch, branch_id)
    branch_label = f"{branch.code} — {branch.name}" if branch else str(branch_id)
    writer.writerow(["phone_number", "first_name", "last_name", "branch"])
    for contact in contacts:
        writer.writerow([contact.phone_number, contact.first_name or "", contact.last_name or "", branch_label])
    output.seek(0)

    filename = f"contacts-{branch_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/groups", response_model=list[ContactGroupOut])
def list_groups(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ContactGroupOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(
            ContactGroup,
            func.count(ContactGroupMember.id),
            func.sum(
                case(
                    (
                        Contact.id.is_not(None)
                        & Contact.consented.is_(True)
                        & Contact.deleted_at.is_(None),
                        1,
                    ),
                    else_=0,
                ),
            ),
        )
        .outerjoin(ContactGroupMember, ContactGroupMember.group_id == ContactGroup.id)
        .outerjoin(Contact, Contact.id == ContactGroupMember.contact_id)
        .where(ContactGroup.branch_id == branch_id, ContactGroup.deleted_at.is_(None))
        .group_by(ContactGroup.id)
        .order_by(ContactGroup.created_at.desc()),
    ).all()
    return [
        ContactGroupOut(
            id=group.id,
            branch_id=group.branch_id,
            name=group.name,
            description=group.description,
            member_count=member_count,
            eligible_member_count=eligible_member_count,
            created_at=group.created_at,
            deleted_at=group.deleted_at,
        )
        for group, member_count, eligible_member_count in rows
    ]


@router.post("/groups", response_model=ContactGroupOut)
def create_group(
    payload: ContactGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactGroupOut:
    assert_branch_access(db, current_user, payload.branch_id)
    name = payload.name.strip()
    existing = db.execute(
        select(ContactGroup).where(ContactGroup.branch_id == payload.branch_id, ContactGroup.name == name),
    ).scalar_one_or_none()
    if existing and existing.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A group with this name already exists")

    group = existing or ContactGroup(branch_id=payload.branch_id, name=name)
    group.name = name
    group.description = payload.description.strip() if payload.description else None
    group.deleted_at = None
    db.add(group)
    db.flush()
    record_audit_event(
        db,
        action="group_created",
        entity_type="contact_group",
        entity_id=str(group.id),
        user_id=current_user.id,
        branch_id=group.branch_id,
    )
    db.commit()
    db.refresh(group)
    return ContactGroupOut.model_validate(group)


@router.get("/groups/{group_id}", response_model=ContactGroupDetailOut)
def get_group(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactGroupDetailOut:
    group = db.get(ContactGroup, group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    assert_branch_access(db, current_user, group.branch_id)
    members = db.execute(
        select(Contact)
        .join(ContactGroupMember, ContactGroupMember.contact_id == Contact.id)
        .where(ContactGroupMember.group_id == group.id, Contact.deleted_at.is_(None))
        .order_by(Contact.first_name.asc(), Contact.last_name.asc(), Contact.phone_number.asc()),
    ).scalars().all()
    return ContactGroupDetailOut(
        id=group.id,
        branch_id=group.branch_id,
        name=group.name,
        description=group.description,
        member_count=len(members),
        eligible_member_count=sum(1 for member in members if member.consented),
        created_at=group.created_at,
        deleted_at=group.deleted_at,
        members=[ContactOut.model_validate(member) for member in members],
    )


@router.put("/groups/{group_id}/members", response_model=ContactGroupDetailOut)
def replace_group_members(
    group_id: uuid.UUID,
    payload: GroupMembersReplace,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactGroupDetailOut:
    group = db.get(ContactGroup, group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    assert_branch_access(db, current_user, group.branch_id)

    contact_ids = list(dict.fromkeys(payload.contact_ids))
    contacts = (
        db.execute(
            select(Contact).where(
                Contact.id.in_(contact_ids),
                Contact.branch_id == group.branch_id,
                Contact.deleted_at.is_(None),
            ),
        ).scalars().all()
        if contact_ids
        else []
    )
    if len(contacts) != len(contact_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more contacts are invalid for this group")

    db.execute(delete(ContactGroupMember).where(ContactGroupMember.group_id == group.id))
    db.add_all(ContactGroupMember(group_id=group.id, contact_id=contact_id) for contact_id in contact_ids)
    record_audit_event(
        db,
        action="group_members_replaced",
        entity_type="contact_group",
        entity_id=str(group.id),
        user_id=current_user.id,
        branch_id=group.branch_id,
        payload={"member_count": len(contact_ids)},
    )
    db.commit()
    return get_group(group_id=group.id, db=db, current_user=current_user)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    group = db.get(ContactGroup, group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    assert_branch_access(db, current_user, group.branch_id)
    group.deleted_at = datetime.now(timezone.utc)
    db.execute(delete(ContactGroupMember).where(ContactGroupMember.group_id == group.id))
    record_audit_event(
        db,
        action="group_deleted",
        entity_type="contact_group",
        entity_id=str(group.id),
        user_id=current_user.id,
        branch_id=group.branch_id,
    )
    db.commit()


@router.post("/groups/{group_id}/members")
def add_group_member(
    group_id: uuid.UUID,
    payload: GroupMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    group = db.get(ContactGroup, group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    assert_branch_access(db, current_user, group.branch_id)
    contact = db.get(Contact, payload.contact_id)
    if contact is None or contact.deleted_at is not None or contact.branch_id != group.branch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contact is invalid for this group")

    existing = db.execute(
        select(ContactGroupMember.id).where(
            ContactGroupMember.group_id == group.id,
            ContactGroupMember.contact_id == contact.id,
        ),
    ).scalar_one_or_none()
    if existing:
        return {"status": "exists"}

    member = ContactGroupMember(group_id=group.id, contact_id=contact.id)
    db.add(member)
    db.flush()
    record_audit_event(
        db,
        action="group_member_added",
        entity_type="contact_group_member",
        entity_id=str(member.id),
        user_id=current_user.id,
        branch_id=group.branch_id,
        payload={"contact_id": str(contact.id)},
    )
    db.commit()
    return {"status": "ok"}


@router.get("/opt-outs")
def list_opt_outs(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, str]]]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(select(OptOut).where(OptOut.branch_id == branch_id).order_by(OptOut.created_at.desc())).scalars()
    return {
        "items": [
            {
                "id": str(row.id),
                "phone_number": row.phone_number,
                "source": row.source.value,
                "reason": row.reason or "",
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.post("/opt-outs")
def create_opt_out(
    payload: OptOutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_branch_access(db, current_user, payload.branch_id)
    existing = db.execute(
        select(OptOut).where(OptOut.branch_id == payload.branch_id, OptOut.phone_number == payload.phone_number),
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            OptOut(
                branch_id=payload.branch_id,
                phone_number=payload.phone_number,
                source=OptOutSource.manual,
                reason=payload.reason,
            ),
        )
        contacts = db.execute(
            select(Contact).where(Contact.branch_id == payload.branch_id, Contact.phone_number == payload.phone_number),
        ).scalars()
        for contact in contacts:
            contact.consented = False
            contact.opted_out_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        action="opt_out_created",
        entity_type="opt_out",
        user_id=current_user.id,
        branch_id=payload.branch_id,
        payload={"phone_number": payload.phone_number},
    )
    db.commit()
    return {"status": "ok"}
