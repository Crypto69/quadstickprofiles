"""Two requests at once: the export file is replaced in one step, and two
profiles that both introduce the same kb_* / ir_* output do not collide."""
import pytest
from sqlalchemy import select
from app import models as M
from app.bridge import ensure_output
from app.routers import profiles as profiles_router
from conftest import FIXTURES, upload


def test_export_replaces_the_share_copy_in_one_step_and_leaves_no_temp_file(client, tmp_path):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    exports = tmp_path / "exports"
    for _ in range(2):                                  # second run overwrites the first
        r = client.get(f"/profiles/{p['id']}/export.csv")
        assert r.status_code == 200
        assert (exports / "ddfortnite.csv").read_bytes() == r.content == (FIXTURES / "ddfortnite.csv").read_bytes()
    assert sorted(x.name for x in exports.iterdir()) == ["ddfortnite.csv"]
    r = client.get(f"/profiles/{p['id']}/export.xlsx")
    assert r.status_code == 200
    assert sorted(x.name for x in exports.iterdir()) == ["ddfortnite.csv", "ddfortnite.xlsx"]


def test_a_failed_export_write_leaves_the_previous_file_untouched(client, tmp_path, monkeypatch):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    exports = tmp_path / "exports"
    assert client.get(f"/profiles/{p['id']}/export.csv").status_code == 200
    good = (exports / "ddfortnite.csv").read_bytes()

    def boom(cfg, path, filename=None, **_):
        open(path, "w").write("half a file")            # partial content, then the writer dies
        raise OSError("disk full")
    monkeypatch.setattr(profiles_router, "write_csv", boom)
    with pytest.raises(OSError):
        client.get(f"/profiles/{p['id']}/export.csv")
    assert (exports / "ddfortnite.csv").read_bytes() == good
    assert sorted(x.name for x in exports.iterdir()) == ["ddfortnite.csv"]


def test_the_response_carries_the_bytes_this_request_wrote(client, tmp_path, monkeypatch):
    """Not a re-read of the shared path, which another export may have replaced meanwhile."""
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    real = profiles_router.write_csv
    exports = tmp_path / "exports"

    def racing(cfg, path, filename=None, **_):
        real(cfg, path, filename)
        (exports / "ddfortnite.csv").write_bytes(b"someone else's export")   # lands first
    monkeypatch.setattr(profiles_router, "write_csv", racing)
    r = client.get(f"/profiles/{p['id']}/export.csv")
    assert r.status_code == 200
    assert r.content == (FIXTURES / "ddfortnite.csv").read_bytes()
    assert (exports / "ddfortnite.csv").read_bytes() == r.content   # ours replaced theirs, whole


def test_prefs_export_is_written_the_same_way(client, tmp_path):
    client.put("/prefs", json={"preferences": {"volume": "40"}})
    r = client.get("/prefs/export.csv")
    assert r.status_code == 200
    exports = tmp_path / "exports"
    assert (exports / "prefs.csv").read_bytes() == r.content
    assert sorted(x.name for x in exports.iterdir()) == ["prefs.csv"]


def test_ensure_output_survives_losing_the_race_for_a_new_keyword(db, monkeypatch):
    """Request A checks the catalog, request B inserts kb_numpad_9 and commits, then A
    inserts too. The identity check cannot see B's row, so the insert must tolerate it."""
    assert db.get(M.OutputCatalog, "kb_numpad_9") is None
    ensure_output(db, "kb_numpad_9")
    db.commit()
    # A's view: the row is not there (stale check), yet the insert must not blow up
    monkeypatch.setattr(db, "get", lambda *a, **k: None)
    ensure_output(db, "kb_numpad_9")
    ensure_output(db, "kb_numpad_9")
    db.commit()
    rows = db.scalars(select(M.OutputCatalog).where(M.OutputCatalog.name == "kb_numpad_9")).all()
    assert len(rows) == 1 and rows[0].grp == "keyboard"
    with pytest.raises(ValueError):
        ensure_output(db, "not_an_output")


def test_two_profiles_introducing_the_same_keyboard_key_both_save(client):
    for name in ("a", "b"):
        r = client.post("/profiles", json={"name": name, "csv_filename": f"{name}.csv",
                                           "modes": [{"name": "M", "mappings": [
                                               {"output": "kb_numpad_8", "inputs": ["lip"]}]}]})
        assert r.status_code == 201, r.text
    assert sum(o["name"] == "kb_numpad_8" for o in client.get("/catalog").json()["outputs"]) == 1
