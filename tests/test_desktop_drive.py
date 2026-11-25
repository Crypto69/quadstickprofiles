"""desktop/desktop_api: what the desktop build reads off the QuadStick drive for a
backup, and how it finds the drive by name. The API checks the same upload again
(api/tests/test_backups.py); this proves the desktop side reads every real file, as
bytes, and nothing else, and that it finds and remembers the right drive."""
import base64
import contextlib
import json
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


# ------------------------------------------------------------- the Mac App Store sandbox
class FakeBookmarks:
    """mac_native.Bookmarks without macOS: a bookmark is the folder's path, and it opens
    only while that folder exists and the test has not taken the permission away."""

    def __init__(self):
        self.revoked = False
        self.opened = 0

    def create(self, folder):
        return str(folder).encode()

    @contextlib.contextmanager
    def open(self, mark):
        root = Path(mark.decode())
        if self.revoked or not root.is_dir():
            yield None
            return
        self.opened += 1
        yield root, None


def sandboxed(tmp_path, monkeypatch, *names):
    vols = drives(tmp_path, *names)
    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: vols)
    data = tmp_path / "data"
    data.mkdir()
    marks = FakeBookmarks()
    return DesktopApi(tmp_path, "http://127.0.0.1:1", data, bookmarks=marks), marks, vols, data


def test_in_the_sandbox_a_drive_not_yet_picked_needs_permission_and_is_never_read(tmp_path, monkeypatch):
    api, marks, vols, data = sandboxed(tmp_path, monkeypatch, "Quad Stick")
    (vols[0][1] / "default.csv").write_bytes(b"QuadStick,a\r\n")
    assert api.quadstick_drive() == {"found": False, "name": "Quad Stick", "files": [],
                                     "needs_permission": True}
    assert api.read_quadstick_drive() is None          # the page then asks for the drive
    with pytest.raises(desktop_api.NotWritten, match="pick Quad Stick once"):
        api.write_quadstick_drive([{"name": "a.csv", "data": base64.b64encode(b"QuadStick").decode()}])
    assert (vols[0][1] / "default.csv").read_bytes() == b"QuadStick,a\r\n"
    assert not (data / "drive.json").exists()


def test_in_the_sandbox_picking_the_drive_once_keeps_a_bookmark_that_opens_it_again(tmp_path, monkeypatch):
    api, marks, vols, data = sandboxed(tmp_path, monkeypatch, "Quad Stick")
    root = vols[0][1]
    (root / "default.csv").write_bytes(b"a")
    asked = {}

    class Window:
        def create_file_dialog(self, kind, directory=""):
            asked["directory"] = directory
            return [str(root)]
    monkeypatch.setitem(sys.modules, "webview", type(sys)("webview"))
    sys.modules["webview"].windows = [Window()]
    sys.modules["webview"].FileDialog = type("FD", (), {"FOLDER": 20})

    state = api.choose_quadstick_drive()
    assert asked["directory"] == str(root)              # opens on the drive: Open is enough
    assert state == {"found": True, "name": "Quad Stick", "files": [{"path": "default.csv", "size": 1}]}
    saved = json.loads((data / "drive.json").read_text())
    assert saved["name"] == "Quad Stick" and base64.b64decode(saved["bookmark"]) == str(root).encode()

    # A later launch: a new shell finds it through the bookmark, with no dialog.
    again = DesktopApi(tmp_path, "http://127.0.0.1:1", data, bookmarks=marks)
    assert as_dict(again.read_quadstick_drive()) == {"default.csv": b"a"}

    # Unplugged: not found, and the bookmark is kept for when it comes back.
    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: [])
    (root / "default.csv").unlink()
    root.rmdir()
    assert again.quadstick_drive() == {"found": False, "name": "Quad Stick", "files": []}
    assert "bookmark" in json.loads((data / "drive.json").read_text())


def test_in_the_sandbox_a_bookmark_macos_no_longer_honours_asks_again(tmp_path, monkeypatch):
    api, marks, vols, data = sandboxed(tmp_path, monkeypatch, "Quad Stick")
    (data / "drive.json").write_text(json.dumps(
        {"name": "Quad Stick", "bookmark": base64.b64encode(str(vols[0][1]).encode()).decode()}))
    assert api.quadstick_drive()["found"] is True
    marks.revoked = True
    assert api.quadstick_drive().get("needs_permission") is True


def test_a_broken_drive_json_is_ignored_not_fatal(tmp_path, monkeypatch):
    api, marks, vols, data = sandboxed(tmp_path, monkeypatch, "Quad Stick")
    for junk in ("[1, 2]", "not json", json.dumps({"name": "Quad Stick", "bookmark": "%%%"})):
        (data / "drive.json").write_text(junk)
        assert api.quadstick_drive().get("needs_permission") is True
