"""desktop/desktop_api: putting profiles on the QuadStick drive. The new files land,
the old profiles go, everything else stays, and a write that cannot finish leaves
the drive as it was."""
import base64
import errno
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
import desktop_api  # noqa: E402
from desktop_api import DesktopApi, NotWritten, check_profiles, replace_profiles  # noqa: E402

P = b"QuadStick Configuration,Version 1.4,\r\n"


def drive(tmp_path, **files):
    root = tmp_path / "Quad Stick"
    root.mkdir()
    for name, data in files.items():
        (root / name.replace("__", "/")).parent.mkdir(parents=True, exist_ok=True)
        (root / name.replace("__", "/")).write_bytes(data)
    return root


def on(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_new_profiles_replace_the_old_and_everything_else_stays(tmp_path):
    root = drive(tmp_path, **{"default.csv": b"old", "cod.csv": b"old", "zelda.csv": b"old",
                              "prefs.csv": b"prefs", "myprefs.csv": b"keep", "joystick.bin": b"\x00\x01",
                              "old__game.csv": b"folder"})
    done = replace_profiles(root, {"default.csv": P + b"d", "apex.csv": P + b"a", "cod.csv": P + b"c"})
    assert on(root) == {"default.csv": P + b"d", "apex.csv": P + b"a", "cod.csv": P + b"c",
                        "prefs.csv": b"prefs", "myprefs.csv": b"keep", "joystick.bin": b"\x00\x01",
                        "old/game.csv": b"folder"}
    assert done == {"written": ["apex.csv", "cod.csv", "default.csv"], "removed": ["zelda.csv"],
                    "kept_default": False}


def test_the_drives_default_stays_when_no_new_profile_is_default(tmp_path):
    root = drive(tmp_path, **{"default.csv": b"boot", "cod.csv": b"old"})
    done = replace_profiles(root, {"apex.csv": P})
    assert on(root) == {"default.csv": b"boot", "apex.csv": P}
    assert done["kept_default"] is True and done["removed"] == ["cod.csv"]


def test_a_name_that_differs_only_in_case_takes_the_new_spelling(tmp_path):
    root = drive(tmp_path, **{"COD.csv": b"old"})
    replace_profiles(root, {"cod.csv": P})
    assert on(root) == {"cod.csv": P}


@pytest.mark.parametrize("files, says", [
    ({}, "at least one"),
    ({"my game.csv": P}, "whitespace"),
    ({"../x.csv": P}, "contains /"),
    ({".x.csv": P}, "dot"),
    ({"cod.txt": P}, "end in .csv"),
    ({"myprefs.csv": P}, "prefs.csv"),
    ({"cod.csv": P, "COD.csv": P}, "Two profiles"),
    ({"cod.csv": b"hello"}, "not a QuadStick profile"),
    ({f"p{i}.csv": P for i in range(33)}, "only 32"),
])
def test_refused_before_anything_is_touched(tmp_path, files, says):
    root = drive(tmp_path, **{"cod.csv": b"old"})
    with pytest.raises(NotWritten, match=says):
        replace_profiles(root, files)
    assert on(root) == {"cod.csv": b"old"}


def test_32_new_profiles_and_the_kept_default_are_too_many(tmp_path):
    root = drive(tmp_path, **{"default.csv": b"boot"})
    with pytest.raises(NotWritten, match="With default.csv"):
        replace_profiles(root, {f"p{i}.csv": P for i in range(32)})
    assert on(root) == {"default.csv": b"boot"}


def test_a_full_drive_is_left_exactly_as_it_was(tmp_path, monkeypatch):
    root = drive(tmp_path, **{"default.csv": b"boot", "cod.csv": b"old"})
    real = desktop_api._write_synced
    calls = []

    def fill_up(path, data):
        calls.append(path)
        if len(calls) == 2:
            raise OSError(errno.ENOSPC, "No space left on device")
        real(path, data)

    monkeypatch.setattr(desktop_api, "_write_synced", fill_up)
    with pytest.raises(NotWritten, match="not enough room.*Nothing was changed"):
        replace_profiles(root, {"apex.csv": P, "zelda.csv": P})
    assert on(root) == {"default.csv": b"boot", "cod.csv": b"old"}   # no temp files left


def shell(tmp_path, monkeypatch, root):
    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: [(root.name, root)])
    return DesktopApi(tmp_path / "exports", "http://127.0.0.1:1", tmp_path)


def b64(data):
    return base64.b64encode(data).decode("ascii")


def test_the_shell_call_writes_and_answers_with_what_is_on_the_drive_now(tmp_path, monkeypatch):
    root = drive(tmp_path, **{"cod.csv": b"old", "prefs.csv": b"p"})
    state = shell(tmp_path, monkeypatch, root).write_quadstick_drive(
        [{"name": "apex.csv", "data": b64(P)}])
    assert state == {"found": True, "name": "Quad Stick",
                     "files": [{"path": "apex.csv", "size": len(P)}, {"path": "prefs.csv", "size": 1}]}


def test_the_shell_call_refuses_when_the_drive_is_not_plugged_in(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop_api, "mounted_volumes", lambda: [])
    api = DesktopApi(tmp_path / "exports", "http://127.0.0.1:1", tmp_path)
    with pytest.raises(NotWritten, match="not plugged in"):
        api.write_quadstick_drive([{"name": "apex.csv", "data": b64(P)}])


def test_the_shell_call_refuses_bytes_that_did_not_arrive_whole(tmp_path, monkeypatch):
    root = drive(tmp_path, **{"cod.csv": b"old"})
    api = shell(tmp_path, monkeypatch, root)
    with pytest.raises(NotWritten, match="did not arrive whole"):
        api.write_quadstick_drive([{"name": "apex.csv", "data": "not base64!"}])
    with pytest.raises(NotWritten, match="twice"):
        api.write_quadstick_drive([{"name": "a.csv", "data": b64(P)}, {"name": "a.csv", "data": b64(P)}])
    assert on(root) == {"cod.csv": b"old"}


def test_check_profiles_takes_a_good_set():
    check_profiles({"default.csv": P, "Cod.csv": P})
