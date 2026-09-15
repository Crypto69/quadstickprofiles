"""API tests run on SQLite by default (no Docker needed). Set
QS_TEST_DATABASE_URL=postgresql+psycopg://... to run the same suite against
Postgres through the real Alembic migration."""
import os
import pathlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

# Importing app.db builds an engine from QS_DATABASE_URL straight away, and the
# default URL needs the psycopg driver, which is an optional extra since the
# desktop build. Point it at this run's database first, so a checkout without
# `api[postgres]` (the SQLite job in CI) can collect the tests at all. The tests
# themselves never use that engine: get_session is overridden below.
os.environ["QS_DATABASE_URL"] = os.environ.get("QS_TEST_DATABASE_URL", "sqlite+pysqlite://")

from app import models  # noqa: E402,F401
from app.db import Base, make_engine, get_session
from app.main import API_PREFIX, app
from app.seed import seed_catalogs, seed_templates
from app.settings import settings

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"
ACTIONS = REPO / "actions"


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    url = os.environ.get("QS_TEST_DATABASE_URL")
    if url:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        from sqlalchemy import text
        eng = make_engine(url)
        with eng.begin() as conn:                      # clean slate, then the real migration
            conn.execute(text("drop schema public cascade; create schema public"))
        os.environ["QS_DATABASE_URL"] = url
        settings.database_url = url
        command.upgrade(AlembicConfig(str(REPO / "api" / "alembic.ini")), "head")
    else:
        db = tmp_path_factory.mktemp("db") / "test.sqlite"
        eng = make_engine(f"sqlite+pysqlite:///{db}")
        Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_db(engine, Session):
    """Fresh profiles for every test; catalogs re-seeded (cheap, idempotent)."""
    with Session() as db:
        for t in ("input_names", "game_actions", "preferences", "mapping_inputs", "mappings", "modes", "profiles"):
            db.execute(Base.metadata.tables[t].delete())
        db.commit()
        seed_catalogs(db)
        seed_templates(db, ACTIONS)
    yield


@pytest.fixture
def client(Session, tmp_path, monkeypatch):
    """Base URL includes API_PREFIX, so the tests below use paths as written in the
    routers ("/profiles", "/catalog") and still exercise the real mounted app."""
    monkeypatch.setattr(settings, "exports_dir", tmp_path / "exports")

    def _session():
        db = Session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_session] = _session
    with TestClient(app, base_url=f"http://testserver{API_PREFIX}") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def root_client(Session, tmp_path, monkeypatch):
    """Unprefixed client, for asserting where things are actually mounted."""
    monkeypatch.setattr(settings, "exports_dir", tmp_path / "exports")

    def _session():
        db = Session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db(Session):
    with Session() as s:
        yield s


def upload(client, path: pathlib.Path, **form):
    with open(path, "rb") as f:
        r = client.post("/profiles/import", files={"file": (path.name, f)}, data=form)
    assert r.status_code == 201, r.text
    return r.json()
