"""
Alembic Environment Configuration

Security notes:
- DATABASE_URL is loaded from environment variables, never hardcoded
- SQLModel metadata is imported so Alembic can detect all table definitions
- The SQLModel workaround (importing all models before running migrations)
  ensures Alembic sees every table defined across the codebase
"""

import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel
from alembic import context

# Add backend directory to path so imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Critical: import ALL models before Alembic autogenerates ─────────────────
# SQLModel only registers tables in metadata when the model classes are imported.
# If you add a new model file, import it here.
from models.orm import (  # noqa: F401 — imports required for side effects
    User,
    UserProfile,
    Transaction,
    MerchantOverride,
    Goal,
    GoalProgressSnapshot,
    Achievement,
    UserAchievement,
    Nudge,
    EducationCard,
    UserEducationCard,
)

# ── Load config ───────────────────────────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Load DATABASE_URL from environment ───────────────────────────────────────
# Never read from alembic.ini — that would require hardcoding credentials
from config import get_settings  # noqa: E402
settings = get_settings()
config.set_main_option("sqlalchemy.url", str(settings.database_url))

# SQLModel's metadata — Alembic uses this to detect schema changes
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Outputs SQL to stdout — useful for reviewing what will run.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Detect column type changes, not just additions/removals
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live DB connection.
    Used in normal operation: `alembic upgrade head`
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool for migrations — no connection reuse
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
