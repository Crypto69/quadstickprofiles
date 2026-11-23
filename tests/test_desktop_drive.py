"""desktop/desktop_api: what the desktop build reads off the QuadStick drive for a
backup, and how it finds the drive by name. The API checks the same upload again
(api/tests/test_backups.py); this proves the desktop side reads every real file, as
bytes, and nothing else, and that it finds and remembers the right drive."""
import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
import desktop_api  # noqa: E402
from desktop_api import (  # noqa: E402
    DesktopApi, FolderTooBig, drive_key, find_drive, list_drive, read_drive, volume_name)


def as_dict(files):
    return {f["path"]: base64.b64decode(f["data"]) for f in files}


def test_every_file_comes_back_byte_for_byte_with_drive_relative_paths(tmp_path):
    (tmp_path / "default.csv").write_bytes(b"QuadStick,a\r\n")
    (tmp_path / "joystick.bin").write_bytes(bytes(range(256)))
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "cod.csv").write_bytes(b"x")
    assert as_dict(read_drive(tmp_path)) == {
        "default.csv": b"QuadStick,a\r\n", "joystick.bin": bytes(range(256)), "old/cod.csv": b"x"}


def test_dot_files_system_folders_and_links_are_left_out(tmp_path):
    (tmp_path / "default.csv").write_bytes(b"a")
    (tmp_path / "._default.csv").write_bytes(b"junk")
    for d in (".Spotlight-V100", ".fseventsd", "System Volume Information", "$RECYCLE.BIN"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "f").write_bytes(b"junk")
    (tmp_path / "link.csv").symlink_to(tmp_path / "default.csv")
    assert list(as_dict(read_drive(tmp_path))) == ["default.csv"]


def test_a_folder_far_bigger_than_a_drive_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop_api, "MAX_FILES", 2)
    for i in range(3):
        (tmp_path / f"p{i}.csv").write_bytes(b"x")
    with pytest.raises(FolderTooBig):
        read_drive(tmp_path)


def test_a_listing_gives_names_and_sizes_and_reads_nothing_else(tmp_path):
    (tmp_path / "default.csv").write_bytes(b"abc")
    (tmp_path / "._default.csv").write_bytes(b"junk")
    assert list_drive(tmp_path) == [{"path": "default.csv", "size": 3}]


def test_the_drive_name_ignores_case_spaces_and_dashes():
    assert drive_key("Quad Stick") == drive_key("QUADSTICK") == drive_key("quad-stick")
    assert drive_key("Quad Sticks") != drive_key("QuadStick")


def drives(tmp_path, *names):
    out = []
    for n in names:
        (tmp_path / n).mkdir()
        out.append((n, tmp_path / n))
    return out


def test_finds_the_remembered_drive_first_then_one_called_quadstick(tmp_path):
    vols = drives(tmp_path, "ExternalHD", "Quad Stick", "MYSTICK")
    assert find_drive(None, vols)[0] == "Quad Stick"
    assert find_drive("mystick", vols)[0] == "MYSTICK"
    assert find_drive("gone", vols)[0] == "Quad Stick"   # remembered one unplugged
    assert find_drive(None, vols[:1]) is None


def test_only_the_top_of_a_drive_has_a_name(tmp_path):
    vols = drives(tmp_path, "Quad Stick")
    assert volume_name(tmp_path / "Quad Stick", vols) == "Quad Stick"
    (tmp_path / "Quad Stick" / "old").mkdir()
    assert volume_name(tmp_path / "Quad Stick" / "old", vols) is None


def test_the_shell_remembers_the_drive_it_found_and_says_what_is_on_it(tmp_path, monkeypatch):
    vols = drives(tmp_path, "Quad Stick")
    (tmp_path / "Quad Stick" / "default.csv").write_bytes(b"a")
    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: vols)
    data = tmp_path / "data"
    data.mkdir()
    api = DesktopApi(tmp_path, "http://127.0.0.1:1", data)

    state = api.quadstick_drive()
    assert state == {"found": True, "name": "Quad Stick",
                     "files": [{"path": "default.csv", "size": 1}]}
    assert (data / "drive.json").read_text() == '{"name": "Quad Stick"}'
    assert as_dict(api.read_quadstick_drive()) == {"default.csv": b"a"}

    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: [])
    assert api.quadstick_drive() == {"found": False, "name": "Quad Stick", "files": []}
    assert api.read_quadstick_drive() is None


def test_a_drive_that_will_not_read_says_so_in_plain_words(tmp_path, monkeypatch):
    vols = drives(tmp_path, "Quad Stick")
    (tmp_path / "Quad Stick" / "default.csv").write_bytes(b"a")
    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: vols)

    def broken(_folder):
        raise OSError(22, "Invalid argument")
    monkeypatch.setattr(desktop_api, "read_drive", broken)
    with pytest.raises(ValueError, match="Could not read the drive Quad Stick"):
        DesktopApi(tmp_path, "http://127.0.0.1:1", None).read_quadstick_drive()
