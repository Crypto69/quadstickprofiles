"""app/standalone.py: the desktop build's SQLite schema path.
create_all + stamp on a fresh file, upgrade head afterwards, refuse anything else."""
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app import models as M
from app.db import Base, make_engine
from app.seed import seed_catalogs, seed_fixtures, seed_templates
from app.standalone import SchemaError, alembic_config, prepare_schema
from conftest import ACTIONS, FIXTURES

# The indexes migrations 0001-0003 create. models.py must declare all of them,
# or a desktop file (create_all + stamp head) is missing them while claiming head.
MIGRATION_INDEXES = {
    "ix_modes_profile_id", "ix_mappings_mode_id", "ix_mappings_kind",
    "ix_preferences_profile_id", "ix_game_actions_profile_id",
    "ix_game_actions_game", "ix_profiles_is_template",
}


@pytest.fixture
def fresh(tmp_path):
    return make_engine(f"sqlite+pysqlite:///{tmp_path / 'studio.sqlite'}")


def index_names(engine, table: str) -> set[str]:
    """Indexes the database actually has, ignoring the ones SQLite invents for
    UNIQUE constraints (those have no counterpart in metadata.indexes)."""
    return {i["name"] for i in inspect(engine).get_indexes(table) if not i["name"].startswith("sqlite_autoindex")}


def test_fresh_database_is_created_and_stamped_then_upgrades_as_a_noop(fresh):
    assert prepare_schema(fresh) == "created"
    tables = set(inspect(fresh).get_table_names())
    assert {"profiles", "modes", "mappings", "preferences", "alembic_version"} <= tables

    head = ScriptDirectory.from_config(alembic_config(fresh)).get_current_head()
    with fresh.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == head

    assert prepare_schema(fresh) == "upgraded"          # second launch
    assert set(inspect(fresh).get_table_names()) == tables


def test_a_created_database_has_exactly_the_indexes_the_models_declare(fresh):
    """create_all must build every index the migrations build. When it does not, a
    later migration touching one of them fails on a shipped desktop install (W9)."""
    prepare_schema(fresh)

    seen = set()
    for table in Base.metadata.sorted_tables:
        declared = {i.name for i in table.indexes}
        assert index_names(fresh, table.name) == declared, table.name
        seen |= declared
    assert seen == MIGRATION_INDEXES


def test_a_desktop_file_created_before_the_fix_gets_the_missing_indexes(fresh):
    """The shape tag v1.0 shipped: tables without indexes, stamped at 0005.
    `prepare_schema` runs 0006, which must fill them in."""
    for table in Base.metadata.sorted_tables:                 # build the pre-fix schema
        table.create(fresh)
        for index in table.indexes:
            index.drop(fresh)
    command.stamp(alembic_config(fresh), "0005_column_b_as_read")
    assert index_names(fresh, "modes") == set()

    assert prepare_schema(fresh) == "upgraded"

    seen = set()
    for table in Base.metadata.sorted_tables:
        seen |= index_names(fresh, table.name)
    assert seen == MIGRATION_INDEXES


def test_tables_without_a_stamp_are_refused(fresh):
    Base.metadata.create_all(fresh)
    with pytest.raises(SchemaError):
        prepare_schema(fresh)


def test_the_seed_runs_on_the_prepared_schema(fresh):
    prepare_schema(fresh)
    with Session(fresh) as db:
        seed_catalogs(db)
        seed_templates(db, ACTIONS)
        seed_fixtures(db, FIXTURES, ACTIONS)
        db.commit()
        assert db.scalar(select(M.Profile.id).limit(1)) is not None
        names = set(db.scalars(select(M.Profile.name)))
    assert len(names) >= 5                                # the shipped fixtures
