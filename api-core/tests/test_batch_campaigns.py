from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.routes.campaigns import MAX_BATCH_ROWS, create_campaign_from_batch_upload
from app.models import MessageQueue
from app.schemas import CampaignBatchRow, CampaignBatchUpload


def test_batch_upload_queues_all_valid_rows(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    result = create_campaign_from_batch_upload(
        payload=CampaignBatchUpload(
            branch_id=branch.id,
            name="Batch",
            timezone="Asia/Manila",
            rows=[
                CampaignBatchRow(phone_number="+639171111111", message_body="First"),
                CampaignBatchRow(phone_number="+639172222222", message_body="Second"),
            ],
        ),
        db=db_session,
        current_user=user,
    )

    queue_count = db_session.execute(select(func.count(MessageQueue.id))).scalar_one()
    assert result["inserted"] == 2
    assert result["queued"] == 2
    assert queue_count == 2


def test_batch_upload_limit_is_ten_thousand_rows(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    row = CampaignBatchRow(phone_number="+639171111111", message_body="Message")

    assert MAX_BATCH_ROWS == 10_000
    with pytest.raises(HTTPException, match="10,000"):
        create_campaign_from_batch_upload(
            payload=CampaignBatchUpload(
                branch_id=branch.id,
                rows=[row] * (MAX_BATCH_ROWS + 1),
            ),
            db=db_session,
            current_user=user,
        )
