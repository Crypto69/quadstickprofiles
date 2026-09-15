from alembic import context
from sqlalchemy import engine_from_config, pool
from app.settings import settings
from app.db import Base
from app import models  # noqa: F401  (registers tables on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


# SQLite cannot ALTER a table to drop or add a constraint, so on SQLite Alembic must
# run in batch mode (copy the table, recreate it). The desktop build upgrades its
# SQLite database through this chain from the stamp onward (app/standalone.py), so
# every migration written after that stamp must work in batch mode as well as on
# Postgres. This is not optional.


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      render_as_batch=settings.database_url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # app/standalone.py hands in the engine it already has (cfg.attributes["engine"]);
    # the CLI and entrypoint.sh build one from QS_DATABASE_URL.
    connectable = config.attributes.get("engine") or engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
        poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=connection.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
