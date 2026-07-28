"""add safe cross-branch modem failover"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_modem_failover"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "failover_policies" not in tables:
        op.create_table(
            "failover_policies",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("offline_after_seconds", sa.Integer(), nullable=False, server_default="90"),
            sa.Column("failover_delay_seconds", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("claim_timeout_seconds", sa.Integer(), nullable=False, server_default="120"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("branch_id", name="uq_failover_policy_branch"),
        )
        op.create_index("ix_failover_policies_branch_id", "failover_policies", ["branch_id"])
    if "failover_routes" not in tables:
        op.create_table(
            "failover_routes",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("source_branch_id", sa.Uuid(), nullable=False),
            sa.Column("backup_branch_id", sa.Uuid(), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["source_branch_id"], ["branches.id"]),
            sa.ForeignKeyConstraint(["backup_branch_id"], ["branches.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_branch_id", "backup_branch_id", name="uq_failover_route_branches"),
        )
        op.create_index("ix_failover_routes_source_branch_id", "failover_routes", ["source_branch_id"])
        op.create_index("ix_failover_routes_backup_branch_id", "failover_routes", ["backup_branch_id"])
        op.create_index("ix_failover_route_pick", "failover_routes", ["backup_branch_id", "enabled", "priority"])
    queue_columns = {column["name"] for column in inspector.get_columns("message_queue")}
    with op.batch_alter_table("message_queue") as batch:
        if "execution_branch_id" not in queue_columns:
            batch.add_column(sa.Column("execution_branch_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_queue_execution_branch", "branches", ["execution_branch_id"], ["id"])
        if "failover_route_id" not in queue_columns:
            batch.add_column(sa.Column("failover_route_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key("fk_queue_failover_route", "failover_routes", ["failover_route_id"], ["id"])
    op.execute(
        sa.text(
            "UPDATE message_queue SET modem_id = NULL "
            "WHERE status = 'pending'",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("message_queue") as batch:
        batch.drop_constraint("fk_queue_failover_route", type_="foreignkey")
        batch.drop_constraint("fk_queue_execution_branch", type_="foreignkey")
        batch.drop_column("failover_route_id")
        batch.drop_column("execution_branch_id")
    op.drop_index("ix_failover_route_pick", table_name="failover_routes")
    op.drop_index("ix_failover_routes_backup_branch_id", table_name="failover_routes")
    op.drop_index("ix_failover_routes_source_branch_id", table_name="failover_routes")
    op.drop_table("failover_routes")
    op.drop_index("ix_failover_policies_branch_id", table_name="failover_policies")
    op.drop_table("failover_policies")
