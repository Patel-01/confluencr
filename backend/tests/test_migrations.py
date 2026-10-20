from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_upgrade_adopts_existing_tables_and_preserves_transaction_data(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy.sqlite3'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE transactions ("
                "transaction_id VARCHAR(255) PRIMARY KEY, "
                "source_account VARCHAR(255) NOT NULL, "
                "destination_account VARCHAR(255) NOT NULL, "
                "amount NUMERIC(18, 2) NOT NULL, currency VARCHAR(3) NOT NULL, "
                "status VARCHAR(10) NOT NULL, created_at DATETIME NOT NULL, "
                "processed_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO transactions VALUES "
                "('txn_existing', 'source', 'destination', 10, 'INR', 'PROCESSING', "
                "'2026-01-01T00:00:00', NULL)"
            )
        )

    migration_config = Config("alembic.ini")
    migration_config.attributes["database_url"] = database_url
    command.upgrade(migration_config, "head")

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT transaction_id, status, attempt_count FROM transactions")
        ).one()
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    table_names = set(inspect(engine).get_table_names())
    engine.dispose()

    assert row == ("txn_existing", "PROCESSING", 0)
    assert revision == "0002_durable_retries"
    assert {"transactions", "client_sessions", "session_activities"} <= table_names
