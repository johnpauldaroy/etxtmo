from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.admin import create_api_key, revoke_api_key
from app.api.routes.campaigns import list_api_key_recipients, list_campaigns
from app.api.routes.sms import get_sms_status, send_sms
from app.core.deps import get_api_key_context
from app.models import Campaign, Contact, OptOut, OptOutSource
from app.schemas import ApiKeyCreate, SmsSendRequest


def _issue_key(db_session, seeded_access, label: str = "Test key"):
    created = create_api_key(
        ApiKeyCreate(branch_id=seeded_access["branch_a"].id, label=label),
        db_session,
        seeded_access["user"],
    )
    db_session.commit()
    return created


def test_send_sms_queues_message_and_status_reflects_it(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    created = _issue_key(db_session, seeded_access)

    api_key = get_api_key_context(db_session, created.api_key)
    assert api_key.branch_id == branch.id

    response = send_sms(SmsSendRequest(to="+639991112222", message="Hello from gateway"), db_session, api_key)
    db_session.commit()

    assert response.status == "queued"
    assert response.to == "+639991112222"
    campaign = db_session.get(Campaign, response.message_id)
    assert campaign.metadata_json["api_key_label"] == "Test key"

    status_response = get_sms_status(response.message_id, db_session, api_key)
    assert status_response.to == "+639991112222"
    assert status_response.status in {"pending", "sending", "sent"}


def test_api_sends_are_labeled_and_listed_as_one_key_history(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    created = _issue_key(db_session, seeded_access, label="POS gateway")
    api_key = get_api_key_context(db_session, created.api_key)

    send_sms(SmsSendRequest(to="+639111111111", message="First"), db_session, api_key)
    send_sms(SmsSendRequest(to="+639222222222", message="Second"), db_session, api_key)
    db_session.commit()

    campaigns = list_campaigns(branch.id, db_session, user)
    api_campaigns = [campaign for campaign in campaigns if campaign.source == "sms_gateway_api"]
    assert len(api_campaigns) == 2
    assert {campaign.api_key_id for campaign in api_campaigns} == {api_key.id}
    assert {campaign.api_key_label for campaign in api_campaigns} == {"POS gateway"}

    history = list_api_key_recipients(api_key.id, branch.id, db_session, user)
    assert history["api_key_label"] == "POS gateway"
    assert {item["phone_number"] for item in history["items"]} == {"+639111111111", "+639222222222"}
    assert all(item["campaign_id"] for item in history["items"])


def test_get_api_key_context_rejects_missing_and_invalid_keys(db_session, seeded_access):
    with pytest.raises(HTTPException) as missing:
        get_api_key_context(db_session, None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as invalid:
        get_api_key_context(db_session, "txm_not-a-real-key")
    assert invalid.value.status_code == 401


def test_revoked_api_key_is_rejected(db_session, seeded_access):
    created = _issue_key(db_session, seeded_access)
    revoke_api_key(created.id, db_session, seeded_access["user"])
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        get_api_key_context(db_session, created.api_key)
    assert exc.value.status_code == 401


def test_send_sms_rejects_opted_out_recipient(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    db_session.add(OptOut(branch_id=branch.id, phone_number="+639991110000", source=OptOutSource.manual))
    db_session.commit()

    created = _issue_key(db_session, seeded_access)
    api_key = get_api_key_context(db_session, created.api_key)

    with pytest.raises(HTTPException) as exc:
        send_sms(SmsSendRequest(to="+639991110000", message="Should be blocked"), db_session, api_key)
    assert exc.value.status_code == 422


def test_api_key_scoped_to_its_branch(db_session, seeded_access):
    branch_a = seeded_access["branch_a"]
    branch_b = seeded_access["branch_b"]
    db_session.add(Contact(branch_id=branch_a.id, phone_number="+639998887777", consented=True))
    db_session.commit()

    created_a = create_api_key(ApiKeyCreate(branch_id=branch_a.id, label="A key"), db_session, seeded_access["superuser"])
    db_session.commit()
    created_b = create_api_key(ApiKeyCreate(branch_id=branch_b.id, label="B key"), db_session, seeded_access["superuser"])
    db_session.commit()

    api_key_a = get_api_key_context(db_session, created_a.api_key)
    response = send_sms(SmsSendRequest(to="+639998887777", message="Hi"), db_session, api_key_a)
    db_session.commit()

    api_key_b = get_api_key_context(db_session, created_b.api_key)
    with pytest.raises(HTTPException) as exc:
        get_sms_status(response.message_id, db_session, api_key_b)
    assert exc.value.status_code == 404
