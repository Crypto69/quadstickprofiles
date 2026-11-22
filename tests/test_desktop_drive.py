"""desktop/desktop_api.read_drive: what the desktop build reads off the QuadStick
drive for a backup. The API checks the same upload again (api/tests/test_backups.py);
this proves the desktop side reads every real file, as bytes, and nothing else."""
import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
import desktop_api  # noqa: E402
from desktop_api import FolderTooBig, read_drive  # noqa: E402


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
