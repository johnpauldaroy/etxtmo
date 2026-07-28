"""remove campaign source from schedule rules"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_rm_schedule_src_campaign"
down_revision = "0004_schedule_source_campaign"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("schedule_rules")}
    if "source_campaign_id" not in columns:
        return

    index_names = {index["name"] for index in inspector.get_indexes("schedule_rules")}
    foreign_key_names = {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys("schedule_rules")
    }
    with op.batch_alter_table("schedule_rules") as batch:
        if "ix_schedule_rules_source_campaign_id" in index_names:
            batch.drop_index("ix_schedule_rules_source_campaign_id")
        if "fk_schedule_rule_source_campaign" in foreign_key_names:
            batch.drop_constraint("fk_schedule_rule_source_campaign", type_="foreignkey")
        batch.drop_column("source_campaign_id")


def downgrade() -> None:
    with op.batch_alter_table("schedule_rules") as batch:
        batch.add_column(sa.Column("source_campaign_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_schedule_rule_source_campaign",
            "campaigns",
            ["source_campaign_id"],
            ["id"],
        )
        batch.create_index("ix_schedule_rules_source_campaign_id", ["source_campaign_id"])
