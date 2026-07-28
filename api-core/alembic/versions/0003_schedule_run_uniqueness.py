"""prevent duplicate schedule rule runs"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_schedule_run_uniqueness"
down_revision = "0002_modem_failover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("schedule_rule_runs")
    }
    if "uq_schedule_rule_run" in unique_constraints:
        return

    op.execute(
        sa.text(
            "DELETE FROM schedule_rule_runs WHERE id IN ("
            "SELECT id FROM ("
            "SELECT id, ROW_NUMBER() OVER (PARTITION BY rule_id, run_at ORDER BY id) AS duplicate_number "
            "FROM schedule_rule_runs"
            ") duplicate_runs WHERE duplicate_number > 1"
            ")",
        ),
    )
    with op.batch_alter_table("schedule_rule_runs") as batch:
        batch.create_unique_constraint("uq_schedule_rule_run", ["rule_id", "run_at"])


def downgrade() -> None:
    with op.batch_alter_table("schedule_rule_runs") as batch:
        batch.drop_constraint("uq_schedule_rule_run", type_="unique")
