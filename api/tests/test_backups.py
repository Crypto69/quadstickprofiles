"""Backups of the QuadStick's flash drive: every file read off the drive is kept
byte for byte, and a restore gives the same bytes back as a .zip."""
import io
import zipfile

import pytest

from app.routers.backups import MAX_FILES
from app.settings import settings
from conftest import FIXTURES

DRIVE = {
    "default.csv": (FIXTURES / "cod.csv").read_bytes(),
    "ddfortnite.csv": (FIXTURES / "ddfortnite.csv").read_bytes(),
    "joystick.bin": bytes(range(256)) * 4,          # not a profile; kept all the same
}


def back_up(client, drive: dict[str, bytes]):
    files = [("files", (p.rsplit("/", 1)[-1] or "unnamed", data)) for p, data in drive.items()]
    return client.post("/backups", files=files, data={"paths": list(drive)})


def unzip(r) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_a_backup_restores_the_very_same_bytes(client):
    r = back_up(client, DRIVE)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["file_count"] == 3
    assert b["total_bytes"] == sum(len(d) for d in DRIVE.values())
    assert [f["path"] for f in b["files"]] == sorted(DRIVE)
    assert b["created_at"].endswith("+00:00")       # the browser turns it into local time

    z = client.get(f"/backups/{b['id']}/download.zip")
    assert z.status_code == 200
    assert z.headers["content-type"] == "application/zip"
    assert unzip(z) == DRIVE


def test_the_zip_is_also_written_to_exports_under_the_name_asked_for(client, tmp_path):
    b = back_up(client, DRIVE).json()
    z = client.get(f"/backups/{b['id']}/download.zip", params={"filename": "quadstick-backup-2026-11-22-1430.zip"})
    assert 'filename="quadstick-backup-2026-11-22-1430.zip"' in z.headers["content-disposition"]
    out = tmp_path / "exports" / "quadstick-backup-2026-11-22-1430.zip"
    assert out.read_bytes() == z.content
    assert z.headers["x-export-path"].endswith("quadstick-backup-2026-11-22-1430.zip")


@pytest.mark.parametrize("name", ["../x.zip", "a b.zip", "backup.csv", "x/y.zip"])
def test_a_zip_name_that_is_not_a_bare_name_is_refused(client, name):
    b = back_up(client, DRIVE).json()
    assert client.get(f"/backups/{b['id']}/download.zip", params={"filename": name}).status_code == 400


def test_the_list_is_newest_first_and_carries_no_bytes(client):
    first = back_up(client, DRIVE).json()
    second = back_up(client, {"default.csv": DRIVE["default.csv"]}).json()
    listed = client.get("/backups").json()
    assert [b["id"] for b in listed] == [second["id"], first["id"]]
    assert listed[0]["files"] == [{"path": "default.csv", "size": len(DRIVE["default.csv"])}]


def test_folders_on_the_drive_are_kept(client):
    drive = {**DRIVE, "old/cod.csv": b"QuadStick,old\r\n"}
    b = back_up(client, drive).json()
    assert unzip(client.get(f"/backups/{b['id']}/download.zip")) == drive


def test_what_the_computer_leaves_on_the_drive_is_left_out(client):
    junk = {".Spotlight-V100/Store-V2/x": b"x", "._default.csv": b"x", ".fseventsd/0001": b"x",
            "System Volume Information/IndexerVolumeGuid": b"x", "$RECYCLE.BIN/desktop.ini": b"x"}
    b = back_up(client, {**DRIVE, **junk}).json()
    assert sorted(f["path"] for f in b["files"]) == sorted(DRIVE)


@pytest.mark.parametrize("path", ["../escape.csv", "/etc/passwd", "a//b.csv", "C:/x.csv", "sub/../x.csv", ""])
def test_a_path_that_could_land_outside_the_drive_is_refused(client, path):
    r = back_up(client, {**DRIVE, path: b"x"})
    assert r.status_code == 400, r.text
    assert client.get("/backups").json() == []


def test_a_backslash_path_is_stored_with_forward_slashes(client):
    b = back_up(client, {**DRIVE, "old\\cod.csv": b"x"}).json()
    assert "old/cod.csv" in [f["path"] for f in b["files"]]


def test_two_names_that_differ_only_in_case_are_refused(client):
    assert back_up(client, {**DRIVE, "DEFAULT.CSV": b"x"}).status_code == 400


def test_a_folder_with_no_csv_at_the_top_is_not_the_quadstick(client):
    r = back_up(client, {"photo.jpg": b"x", "sub/a.csv": b"x"})
    assert r.status_code == 422
    assert "not the QuadStick drive" in r.json()["detail"]
    assert client.get("/backups").json() == []


def test_paths_must_match_files(client):
    r = client.post("/backups", files=[("files", ("a.csv", b"x"))], data={"paths": ["a.csv", "b.csv"]})
    assert r.status_code == 400


def test_too_many_files_is_refused(client):
    drive = {f"p{i}.csv": b"x" for i in range(MAX_FILES + 1)}
    assert back_up(client, drive).status_code == 413


def test_too_many_bytes_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "max_backup_bytes", 1000)
    assert back_up(client, DRIVE).status_code == 413
    assert client.get("/backups").json() == []


def test_a_backup_can_be_deleted(client):
    b = back_up(client, DRIVE).json()
    assert client.delete(f"/backups/{b['id']}").status_code == 204
    assert client.get("/backups").json() == []
    assert client.get(f"/backups/{b['id']}/download.zip").status_code == 404
    assert client.delete(f"/backups/{b['id']}").status_code == 404
