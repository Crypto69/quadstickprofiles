"""W7: an import must not buffer an unbounded body in memory.

Two halves, both wired: `read_capped` itself, and the two import routers that
call it after their 415 extension check.
"""
import io

import anyio
import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.settings import settings
from app.uploads import read_capped

from conftest import FIXTURES


def _upload(data: bytes, filename: str = "big.csv") -> UploadFile:
    """An UploadFile whose `.size` is set, the way the multipart parser sets it."""
    return UploadFile(file=io.BytesIO(data), filename=filename, size=len(data),
                      headers=Headers({"content-type": "text/csv"}))


def _sizeless(data: bytes, filename: str = "big.csv") -> UploadFile:
    """`.size` is a hint; prove the chunk loop catches an upload that lies."""
    return UploadFile(file=io.BytesIO(data), filename=filename,
                      headers=Headers({"content-type": "text/csv"}))


def _read(*args, **kw) -> bytes:
    """`read_capped` is a coroutine and there is no async pytest plugin here, so
    drive it on a one-shot event loop."""
    return anyio.run(lambda: read_capped(*args, **kw))


# ------------------------------------------------------------------- read_capped

def test_a_small_upload_is_returned_whole():
    assert _read(_upload(b"a,b,c\r\n"), limit=1024) == b"a,b,c\r\n"


def test_an_upload_at_exactly_the_limit_is_allowed():
    data = b"x" * 1024
    assert _read(_upload(data), limit=1024) == data


def test_a_declared_size_over_the_limit_is_refused_without_reading():
    with pytest.raises(HTTPException) as e:
        _read(_upload(b"x" * 2048), limit=1024)
    assert e.value.status_code == 413
    assert "big.csv" in e.value.detail


def test_an_undeclared_size_is_caught_by_the_chunk_loop():
    with pytest.raises(HTTPException) as e:
        _read(_sizeless(b"x" * 2048), limit=1024, chunk=64)
    assert e.value.status_code == 413


def test_the_limit_defaults_to_the_setting_read_at_call_time(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 16)
    with pytest.raises(HTTPException) as e:
        _read(_upload(b"x" * 64))
    assert e.value.status_code == 413
    monkeypatch.setattr(settings, "max_upload_bytes", 4096)
    assert len(_read(_upload(b"x" * 64))) == 64


def test_every_fixture_is_comfortably_under_the_cap():
    """The cap must never refuse a real profile. The biggest .xlsx is ~61 KB."""
    biggest = max((p.stat().st_size, p.name)
                  for p in FIXTURES.iterdir() if p.suffix in (".csv", ".xlsx"))
    assert biggest[0] < settings.max_upload_bytes / 4, biggest


# ------------------------------------------------------- the routers (not wired yet)

def test_profile_import_refuses_an_oversized_upload(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    before = len(client.get("/profiles").json())
    r = client.post("/profiles/import", files={"file": ("huge.csv", b"x" * 2048)})
    assert r.status_code == 413, r.text
    assert len(client.get("/profiles").json()) == before


def test_prefs_import_refuses_an_oversized_upload(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    before = client.get("/prefs").json()
    r = client.post("/prefs/import", files={"file": ("prefs.csv", b"x" * 2048)})
    assert r.status_code == 413, r.text
    assert client.get("/prefs").json() == before


def test_a_real_fixture_still_imports_under_the_default_cap(client):
    """Guards the wiring from the other direction: whether or not read_capped is
    in the routers yet, a real profile must import."""
    with open(FIXTURES / "ddfortnite.csv", "rb") as f:
        r = client.post("/profiles/import", files={"file": ("ddfortnite.csv", f)})
    assert r.status_code == 201, r.text
