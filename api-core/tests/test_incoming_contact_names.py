from __future__ import annotations

from datetime import datetime, timezone

from app.api.routes.incoming import list_incoming
from app.models import Contact, IncomingMessage


def test_incoming_message_resolves_contact_name_across_ph_phone_formats(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    db_session.add_all(
        [
            Contact(
                branch_id=branch.id,
                phone_number="09171234567",
                first_name="Juan",
                last_name="Dela Cruz",
                consented=True,
            ),
            IncomingMessage(
                branch_id=branch.id,
                phone_number="+639171234567",
                message_text="Hello",
                received_at=datetime.now(timezone.utc),
                processed=False,
            ),
        ],
    )
    db_session.commit()

    rows = list_incoming(branch_id=branch.id, db=db_session, current_user=user)

    assert len(rows) == 1
    assert rows[0].contact_name == "Juan Dela Cruz"
    assert rows[0].phone_number == "+639171234567"
