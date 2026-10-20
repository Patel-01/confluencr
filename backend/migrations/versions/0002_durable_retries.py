import sqlalchemy as sa
from alembic import op

revision = "0002_durable_retries"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("transactions")}
    with op.batch_alter_table("transactions") as batch:
        if "attempt_count" not in columns:
            batch.add_column(
                sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
            )
        if "next_attempt_at" not in columns:
            batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
        if "lease_until" not in columns:
            batch.add_column(sa.Column("lease_until", sa.DateTime(timezone=True)))
        if "lease_token" not in columns:
            batch.add_column(sa.Column("lease_token", sa.String(length=36)))
        if "last_error" not in columns:
            batch.add_column(sa.Column("last_error", sa.Text()))
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("transactions")}
    if "ix_transactions_queue" not in indexes:
        op.create_index(
            "ix_transactions_queue",
            "transactions",
            ["status", "next_attempt_at", "lease_until"],
        )


def downgrade() -> None:
    op.drop_index("ix_transactions_queue", table_name="transactions")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("last_error")
        batch.drop_column("lease_token")
        batch.drop_column("lease_until")
        batch.drop_column("next_attempt_at")
        batch.drop_column("attempt_count")
