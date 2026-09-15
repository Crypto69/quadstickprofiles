"""Schema for a standalone database: the desktop build's SQLite file.

A fresh database gets its tables from the models
(`Base.metadata.create_all`, the path the whole test suite runs on) and is stamped at
the Alembic head. Every later launch runs `alembic upgrade head`, so a migration
written after that stamp must run on SQLite (batch mode, see alembic/env.py) as well
as on Postgres.

`alembic upgrade head` on an *empty* SQLite database is not a supported path: the
five migrations before the stamp are Postgres-only (0001 creates a JSONB column and
a `~` regex CHECK, 0004 is written in Postgres SQL). That is why this module exists."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from . import models  # noqa: F401  (registers every table on Base.metadata)
from .db import Base

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"


class SchemaError(RuntimeError):
    """The database is in a state this module refuses to touch."""


def alembic_config(engine: Engine, script_location: Path = ALEMBIC_DIR) -> Config:
    """An Alembic config that needs no alembic.ini (its %(here)s is wrong when frozen)
    and reuses the engine we already have instead of rebuilding one from the URL."""
    cfg = Config()
    cfg.set_main_option("script_location", str(script_location))
    cfg.attributes["engine"] = engine
    return cfg


def prepare_schema(engine: Engine, script_location: Path = ALEMBIC_DIR) -> str:
    """Bring the database to the current schema. Returns "created" for a fresh
    database and "upgraded" when the migration chain ran (possibly a no-op)."""
    tables = set(inspect(engine).get_table_names())
    cfg = alembic_config(engine, script_location)
    if "alembic_version" in tables:
        command.upgrade(cfg, "head")
        return "upgraded"
    if tables:
        raise SchemaError(
            "The database already has tables but no Alembic stamp. Refusing to create "
            "tables over existing data. If this is a copy of a NAS database, run "
            "`alembic upgrade head` against it with the Postgres driver instead.")
    Base.metadata.create_all(engine)
    command.stamp(cfg, "head")
    return "created"
