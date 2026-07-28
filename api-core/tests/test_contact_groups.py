from __future__ import annotations

from app.api.routes.contacts import create_group, delete_group, get_group, list_groups, replace_group_members
from sqlalchemy import select

from app.models import Campaign, CampaignRecipient, CampaignStatus, Contact
from app.schemas import ContactGroupCreate, GroupMembersReplace
from app.services.queue import expand_recipients_for_campaign


def test_contact_group_create_and_replace_members(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    contacts = [
        Contact(
            branch_id=branch.id,
            phone_number=f"+63917123456{index}",
            first_name=f"Member {index}",
            consented=index == 0,
        )
        for index in range(2)
    ]
    db_session.add_all(contacts)
    db_session.commit()

    group = create_group(
        payload=ContactGroupCreate(branch_id=branch.id, name="Loan Members", description="Active borrowers"),
        db=db_session,
        current_user=user,
    )
    detail = replace_group_members(
        group_id=group.id,
        payload=GroupMembersReplace(contact_ids=[contact.id for contact in contacts]),
        db=db_session,
        current_user=user,
    )

    assert detail.member_count == 2
    assert detail.eligible_member_count == 1
    assert {member.id for member in detail.members} == {contact.id for contact in contacts}
    listed_group = list_groups(branch_id=branch.id, db=db_session, current_user=user)[0]
    assert listed_group.member_count == 2
    assert listed_group.eligible_member_count == 1

    campaign = Campaign(
        branch_id=branch.id,
        name="Group campaign",
        status=CampaignStatus.draft,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    db_session.add(campaign)
    db_session.flush()
    recipient_count = expand_recipients_for_campaign(
        db_session,
        campaign,
        group_id=group.id,
        raw_message="Group message",
    )
    recipients = db_session.execute(
        select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id),
    ).scalars().all()
    assert recipient_count == 1
    assert [recipient.contact_id for recipient in recipients] == [contacts[0].id]

    delete_group(group_id=group.id, db=db_session, current_user=user)
    assert list_groups(branch_id=branch.id, db=db_session, current_user=user) == []


def test_deleted_contact_group_can_be_recreated_with_same_name(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    original = create_group(
        payload=ContactGroupCreate(branch_id=branch.id, name="Reminders"),
        db=db_session,
        current_user=user,
    )
    delete_group(group_id=original.id, db=db_session, current_user=user)

    restored = create_group(
        payload=ContactGroupCreate(branch_id=branch.id, name="Reminders", description="Restored"),
        db=db_session,
        current_user=user,
    )

    assert restored.id == original.id
    assert get_group(group_id=restored.id, db=db_session, current_user=user).description == "Restored"
