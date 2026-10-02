import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# 1. Resolve project root directory dynamically
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 2. Load .env.development
env_path = os.path.join(BASE_DIR, ".env.development")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

from app.models import Base

config = context.config

# 3. Inject DATABASE_URL
raw_url = os.environ.get("DATABASE_URL")
if not raw_url:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

sync_url = raw_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def on_version_apply(ctx, step, heads, run_args):
    """Callback to store migration message in alembic_version table."""
    if step.is_upgrade:
        doc = (step.revision_map.get_revision(step.up_revision_id).doc or "").replace("'", "''")
        conn = ctx.connection
        conn.execute(
            text(f"UPDATE alembic_version SET description = '{doc}' WHERE version_num = '{step.up_revision_id}';")
        )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # 1. Ensure alembic_version exists with description column & commit
        connection.execute(
            text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            );
            ALTER TABLE alembic_version ADD COLUMN IF NOT EXISTS description VARCHAR(255);
            """)
        )
        connection.commit()  # Commit structural changes immediately

        # 2. Configure Alembic context
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            on_version_apply=on_version_apply
        )

        # 3. Run migrations and commit transaction
        with context.begin_transaction():
            context.run_migrations()

        connection.commit()  # Commit the transaction to PostgreSQL


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()