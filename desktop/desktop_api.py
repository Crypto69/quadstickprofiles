"""What the web app may ask the desktop shell to do (window.pywebview.api).

Three calls, all narrow on purpose: reveal a file the API wrote into the exports
folder, open one of this app's own URLs in the system browser (that is where
printing happens; a WebView has no print dialog and cannot open tabs), and read
the files off a folder the user picks (the QuadStick's flash drive, for a backup).
The last exists because a WebView's file input cannot choose a folder: pywebview
answers `<input webkitdirectory>` with a file panel."""
import base64
import logging
import os
import subprocess
import webbrowser
from pathlib import Path

from host_os import IS_MAC, IS_WINDOWS

log = logging.getLogger("desktop.api")

# Kept in step with api/app/routers/backups.py, which refuses the same things; here
# they only stop a wrong folder (a home directory) being read into memory at all.
MAX_FILES = 500
MAX_BYTES = 20 * 1024 * 1024
SYSTEM_FOLDERS = {"system volume information", "$recycle.bin"}


class FolderTooBig(ValueError):
    pass


def read_drive(folder: Path) -> list[dict]:
    """Every file under `folder` as {path, data}: `path` relative and '/'-separated,
    `data` base64. Dot-files and the folders a computer leaves on a removable drive
    are skipped (the firmware deletes dot-files at boot); links are not followed."""
    folder = Path(folder)
    files, total = [], 0
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d.lower() not in SYSTEM_FOLDERS)
        for name in sorted(names):
            p = Path(root) / name
            if name.startswith(".") or p.is_symlink() or not p.is_file():
                continue
            data = p.read_bytes()
            total += len(data)
            if len(files) >= MAX_FILES or total > MAX_BYTES:
                raise FolderTooBig("That folder holds far more than a QuadStick drive does. "
                                   "Pick the QuadStick drive itself.")
            files.append({"path": p.relative_to(folder).as_posix(),
                          "data": base64.b64encode(data).decode("ascii")})
    return files


class DesktopApi:
    def __init__(self, exports_dir: Path, origin: str):
        self._exports = Path(exports_dir).resolve()
        self._origin = origin.rstrip("/")

    def reveal(self, path: str) -> None:
        target = Path(path).resolve()
        if self._exports not in target.parents or not target.is_file():
            log.warning("reveal refused: %s", path)
            return
        log.info("reveal %s", target)
        if IS_MAC:
            subprocess.Popen(["open", "-R", str(target)])
        elif IS_WINDOWS:
            subprocess.Popen(["explorer", f"/select,{target}"])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])

    def pick_drive_files(self) -> list[dict] | None:
        """Ask for a folder and return its files (see `read_drive`), or None when the
        dialog is cancelled. A folder that is too big raises; pywebview rejects the
        JavaScript promise with its message."""
        import webview
        picked = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        if not picked:
            return None
        folder = Path(picked[0] if isinstance(picked, (list, tuple)) else picked)
        log.info("reading drive folder %s", folder)
        return read_drive(folder)

    def open_external(self, url: str) -> None:
        if not url.startswith(self._origin + "/"):
            log.warning("open_external refused: %s", url)
            return
        log.info("open_external %s", url)
        webbrowser.open(url)
