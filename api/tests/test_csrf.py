"""W8: the API refuses cross-origin state changes.

Single-user means no login, so there is no session to protect — but the API is
reachable from the LAN and a multipart POST is a "simple" request any page can
make. `app/csrf.py` refuses a mutating request whose `Origin` names a different
host, and requires the custom `X-Requested-With` header the SPA sends.

The clients here are deliberately *not* the conftest `client`/`root_client`
fixtures: those carry the SPA header on every request, which is exactly what these
tests need to withhold.
"""
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.csrf import HEADER, REQUESTED_WITH
from app.db import get_session
from app.main import API_PREFIX, app
from app.settings import settings

from conftest import FIXTURES

SPA = {HEADER: REQUESTED_WITH}
NEW_PROFILE = {"name": "Guard test", "csv_filename": "guardtest.csv"}


@pytest.fixture
def bare(Session, tmp_path, monkeypatch):
    """A client that sends *no* headers of its own, so each test adds exactly the
    ones it is about."""
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


def _count(bare) -> int:
    r = bare.get("/profiles")
    assert r.status_code == 200, r.text
    return len(r.json())


# ------------------------------------------------------------------- the Origin layer

def test_a_post_from_another_site_is_refused_and_creates_nothing(bare):
    before = _count(bare)
    r = bare.post("/profiles", json=NEW_PROFILE,
                  headers={**SPA, "Origin": "http://evil.example"})
    assert r.status_code == 403
    assert "Cross-origin" in r.json()["detail"]
    assert _count(bare) == before


def test_origin_null_is_refused(bare):
    """A sandboxed iframe or a file:// page sends Origin: null."""
    r = bare.post("/profiles", json=NEW_PROFILE, headers={**SPA, "Origin": "null"})
    assert r.status_code == 403
    assert "Cross-origin" in r.json()["detail"]


def test_the_ports_may_differ_because_nginx_forwards_host_without_one(bare):
    """web/nginx.conf proxies with `$host`, so the API sees `Host: nas` while the
    browser sent `Origin: http://nas:8324`. Hostnames only, or the SPA 403s."""
    r = bare.post("/profiles", json=NEW_PROFILE,
                  headers={**SPA, "Origin": "http://testserver:8324"})
    assert r.status_code == 201, r.text


def test_a_matching_origin_with_https_is_accepted(bare):
    r = bare.post("/profiles", json={**NEW_PROFILE, "csv_filename": "guardtls.csv"},
                  headers={**SPA, "Origin": "https://testserver"})
    assert r.status_code == 201, r.text


# ----------------------------------------------------- the X-Requested-With layer

def test_a_post_without_the_custom_header_is_refused(bare):
    """No Origin at all — a form post, or a plain curl. The custom header is what
    a cross-origin form cannot produce without a preflight."""
    before = _count(bare)
    r = bare.post("/profiles", json=NEW_PROFILE)
    assert r.status_code == 403
    assert HEADER in r.json()["detail"]
    assert _count(bare) == before


def test_a_wrong_header_value_is_refused(bare):
    r = bare.post("/profiles", json=NEW_PROFILE, headers={HEADER: "XMLHttpRequest"})
    assert r.status_code == 403


@pytest.mark.parametrize("method,path", [
    ("PUT", "/prefs"),
    ("DELETE", "/profiles/1"),
    ("PATCH", "/profiles/1"),
])
def test_every_mutating_method_is_guarded(bare, method, path):
    assert bare.request(method, path, json={"preferences": {}}).status_code == 403


def test_multipart_import_without_the_header_is_refused(bare):
    """The remote path this whole guard exists for: a hidden form can post
    multipart cross-origin with no preflight."""
    before = _count(bare)
    with open(FIXTURES / "ddfortnite.csv", "rb") as f:
        r = bare.post("/profiles/import", files={"file": ("ddfortnite.csv", f)})
    assert r.status_code == 403
    assert _count(bare) == before


def test_prefs_import_without_the_header_is_refused(bare):
    prefs = pathlib.Path(FIXTURES / "ddfortnite.csv")       # content never reaches the parser
    with open(prefs, "rb") as f:
        r = bare.post("/prefs/import", files={"file": ("prefs.csv", f)})
    assert r.status_code == 403


def test_the_spa_header_alone_is_enough(bare):
    """What the app itself sends: the header, and no Origin (same-origin fetch in
    some browsers) — accepted."""
    r = bare.post("/profiles", json={**NEW_PROFILE, "csv_filename": "guardspa.csv"},
                  headers=SPA)
    assert r.status_code == 201, r.text


# --------------------------------------------------------------------- safe methods

def test_reads_are_never_guarded(bare):
    """GET must keep working for anyone: the card and the summary are opened in a
    new tab, which sends no custom header."""
    for path in ("/health", "/catalog", "/profiles"):
        assert bare.get(path, headers={"Origin": "http://evil.example"}).status_code == 200


def test_the_unprefixed_health_check_is_not_guarded(Session, tmp_path, monkeypatch):
    """Docker's health check and the NAS reverse proxy hit /health outside /api."""
    monkeypatch.setattr(settings, "exports_dir", tmp_path / "exports")
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
