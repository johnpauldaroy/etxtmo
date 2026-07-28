"""allow schedule rules to reuse campaigns"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_schedule_source_campaign"
down_revision = "0003_schedule_run_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("schedule_rules")}
    if "source_campaign_id" not in columns:
        with op.batch_alter_table("schedule_rules") as batch:
            batch.add_column(sa.Column("source_campaign_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key(
                "fk_schedule_rule_source_campaign",
                "campaigns",
                ["source_campaign_id"],
                ["id"],
            )
            batch.create_index("ix_schedule_rules_source_campaign_id", ["source_campaign_id"])


def downgrade() -> None:
    with op.batch_alter_table("schedule_rules") as batch:
        batch.drop_index("ix_schedule_rules_source_campaign_id")
        batch.drop_constraint("fk_schedule_rule_source_campaign", type_="foreignkey")
        batch.drop_column("source_campaign_id")
