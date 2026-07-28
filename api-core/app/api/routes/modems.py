from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import Modem, ModemStatus, NodeHeartbeat, SimCard, User
from app.schemas import ModemCreate, ModemOut, SimCardCreate, SimCardOut
from app.services.audit import record_audit_event
from app.services.queue import effective_modem_status

router = APIRouter(prefix="/modems", tags=["modems"])


@router.get("", response_model=list[ModemOut])
def list_modems(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ModemOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(Modem).where(Modem.branch_id == branch_id).order_by(Modem.created_at.desc()),
    ).scalars()
    results = []
    for row in rows:
        out = ModemOut.model_validate(row)
        out.status = effective_modem_status(row)
        results.append(out)
    return results


@router.post("", response_model=ModemOut)
def create_modem(
    payload: ModemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModemOut:
    assert_branch_access(db, current_user, payload.branch_id)

    existing = None
    if payload.imei:
        existing = db.execute(select(Modem).where(Modem.imei == payload.imei)).scalar_one_or_none()
    if existing is not None and existing.branch_id != payload.branch_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This modem IMEI is already registered to another branch",
        )

    if existing is None:
        modem = Modem(**payload.model_dump(), status=ModemStatus.offline)
        db.add(modem)
        action = "modem_registered"
    else:
        modem = existing
        modem.node_name = payload.node_name
        modem.name = payload.name
        modem.port = payload.port
        action = "modem_updated"

    db.flush()
    record_audit_event(
        db,
        action=action,
        entity_type="modem",
        entity_id=str(modem.id),
        user_id=current_user.id,
        branch_id=payload.branch_id,
    )
    db.commit()
    db.refresh(modem)
    return ModemOut.model_validate(modem)


@router.delete("/{modem_id}")
def delete_modem(
    modem_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    modem = db.get(Modem, modem_id)
    if modem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modem not found")
    assert_branch_access(db, current_user, modem.branch_id)

    branch_id = modem.branch_id
    db.delete(modem)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This modem has message history and cannot be deleted.",
        ) from None

    record_audit_event(
        db,
        action="modem_deleted",
        entity_type="modem",
        entity_id=str(modem_id),
        user_id=current_user.id,
        branch_id=branch_id,
    )
    db.commit()
    return {"status": "deleted"}


@router.get("/heartbeats")
def list_heartbeats(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, str]]]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(NodeHeartbeat).where(NodeHeartbeat.branch_id == branch_id).order_by(NodeHeartbeat.last_seen_at.desc()).limit(200),
    ).scalars()
    return {
        "items": [
            {
                "node_name": row.node_name,
                "status": row.status,
                "last_seen_at": row.last_seen_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/sim-cards", response_model=list[SimCardOut])
def list_sim_cards(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SimCardOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(SimCard).where(SimCard.branch_id == branch_id).order_by(SimCard.created_at.desc()),
    ).scalars()
    return [SimCardOut.model_validate(row) for row in rows]


@router.post("/sim-cards", response_model=SimCardOut)
def create_sim_card(
    payload: SimCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SimCardOut:
    assert_branch_access(db, current_user, payload.branch_id)
    sim = SimCard(**payload.model_dump())
    db.add(sim)
    db.flush()
    record_audit_event(
        db,
        action="sim_card_registered",
        entity_type="sim_card",
        entity_id=str(sim.id),
        user_id=current_user.id,
        branch_id=sim.branch_id,
    )
    db.commit()
    db.refresh(sim)
    return SimCardOut.model_validate(sim)

