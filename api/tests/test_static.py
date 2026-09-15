"""app/spa.py: the desktop build serves web/dist itself. Mirrors web/nginx.conf."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.spa import IMMUTABLE, mount_spa


@pytest.fixture
def spa(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>")
    (dist / "assets" / "app.js").write_text("export {}")
    (dist / "assets" / "font.woff2").write_bytes(b"wOF2")
    (dist / "favicon.ico").write_bytes(b"ico")
    (tmp_path / "secret.txt").write_text("outside the dist root")

    app = FastAPI()

    @app.get("/api/health")
    def api_health():
        return {"status": "ok"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    mount_spa(app, dist)
    return TestClient(app)


def test_index_and_deep_links_get_the_app(spa):
    for path in ("/", "/profiles/3", "/learn/some-topic", "/device"):
        r = spa.get(path)
        assert r.status_code == 200 and "<title>spa</title>" in r.text, path
        assert r.headers["cache-control"] == "no-cache"


def test_api_routes_still_win(spa):
    assert spa.get("/api/health").json() == {"status": "ok"}
    assert spa.get("/health").json() == {"status": "ok"}
    assert spa.get("/api/nope").status_code == 404        # not an app route


def test_assets_are_immutable_and_typed(spa):
    r = spa.get("/assets/app.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == IMMUTABLE
    assert r.headers["content-type"].startswith("text/javascript")
    assert spa.get("/assets/font.woff2").headers["content-type"].startswith("font/woff2")


def test_unknown_asset_is_a_404_not_the_app(spa):
    assert spa.get("/assets/missing.js").status_code == 404


def test_real_files_at_the_root_are_served(spa):
    r = spa.get("/favicon.ico")
    assert r.status_code == 200 and r.content == b"ico"


def test_paths_outside_the_root_fall_back_to_the_app(spa):
    r = spa.get("/%2e%2e/secret.txt")
    assert r.status_code == 200 and "outside" not in r.text


def test_missing_index_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        mount_spa(FastAPI(), tmp_path)
