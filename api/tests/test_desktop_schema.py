"""app/standalone.py: the desktop build's SQLite schema path.
create_all + stamp on a fresh file, upgrade head afterwards, refuse anything else."""
import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app import models as M
from app.db import Base, make_engine
from app.seed import seed_catalogs, seed_fixtures, seed_templates
from app.standalone import SchemaError, alembic_config, prepare_schema
from conftest import ACTIONS, FIXTURES


@pytest.fixture
def fresh(tmp_path):
    return make_engine(f"sqlite+pysqlite:///{tmp_path / 'studio.sqlite'}")


def test_fresh_database_is_created_and_stamped_then_upgrades_as_a_noop(fresh):
    assert prepare_schema(fresh) == "created"
    tables = set(inspect(fresh).get_table_names())
    assert {"profiles", "modes", "mappings", "preferences", "alembic_version"} <= tables

    head = ScriptDirectory.from_config(alembic_config(fresh)).get_current_head()
    with fresh.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar() == head

    assert prepare_schema(fresh) == "upgraded"          # second launch
    assert set(inspect(fresh).get_table_names()) == tables


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
