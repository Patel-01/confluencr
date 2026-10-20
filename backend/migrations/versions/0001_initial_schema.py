import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("transactions"):
        op.create_table(
            "transactions",
            sa.Column("transaction_id", sa.String(255), primary_key=True),
            sa.Column("source_account", sa.String(255), nullable=False),
            sa.Column("destination_account", sa.String(255), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not inspector.has_table("client_sessions"):
        op.create_table(
            "client_sessions",
            sa.Column("session_id", sa.String(64), primary_key=True),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("total_api_calls", sa.Integer(), nullable=False, server_default="0"),
        )
    if not inspector.has_table("session_activities"):
        op.create_table(
            "session_activities",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "session_id",
                sa.String(64),
                sa.ForeignKey("client_sessions.session_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("path", sa.String(255), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_session_activities_session_id", "session_activities", ["session_id"]
        )


def downgrade() -> None:
    # This baseline may adopt a pre-existing database; dropping its tables is unsafe.
    pass
