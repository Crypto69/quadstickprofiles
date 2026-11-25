"""What the web app may ask the desktop shell to do (window.pywebview.api).

All narrow on purpose: reveal a file the API wrote into the exports folder, open one
of this app's own URLs in the system browser (that is where printing happens; a
WebView has no print dialog and cannot open tabs), and the QuadStick's flash drive.

The drive calls exist because the desktop app, unlike a web page, can see what is
plugged in. It finds the drive by its name ("Quad Stick" as macOS shows it,
"QUADSTICK" on Windows: any case, spaces and dashes ignored), remembers the name in
`drive.json`, and lists or reads it without a folder dialog. Only when it cannot find
one does it ask, and then it remembers the name of the drive that was picked. A
WebView's file input could not do that part either: pywebview answers
`<input webkitdirectory>` with a file panel.

One call writes to the drive: `write_quadstick_drive` puts a set of profiles on it in
place of the ones there now (`replace_profiles`). The web page backs the drive up
first; this side checks every name again, writes the new files before it removes
anything, and flushes before it answers, so "done" means safe to unplug.

The Mac App Store build runs in Apple's sandbox, where a mounted drive may be seen
but not opened. There the drive is still found by name, but it is opened through a
bookmark (`mac_native`) that only picking it in the folder dialog creates. Until it
has been picked once, `quadstick_drive` answers `needs_permission` and the page says
to choose it; after that it works as above, every launch, for that drive."""
import base64
import binascii
import errno
import json
import logging
import os
import re
import subprocess
import webbrowser
from contextlib import contextmanager
from pathlib import Path

from qsprofile.catalog import check_csv_filename

from host_os import IS_MAC, IS_WINDOWS

if IS_MAC:
    import mac_native
    SANDBOXED = mac_native.SANDBOXED
else:
    mac_native = None
    SANDBOXED = False

log = logging.getLogger("desktop.api")

# Kept in step with api/app/routers/backups.py, which refuses the same things; here
# they only stop a wrong folder (a home directory) being read into memory at all.
MAX_FILES = 500
MAX_BYTES = 20 * 1024 * 1024
SYSTEM_FOLDERS = {"system volume information", "$recycle.bin"}


class FolderTooBig(ValueError):
    pass


def _drive_files(folder: Path):
    """(drive-relative '/'-path, file) for every real file under `folder`. Dot-files
    and the folders a computer leaves on a removable drive are skipped (the firmware
    deletes dot-files at boot); links are not followed. Refuses a folder far bigger
    than a QuadStick drive, so a home directory is never walked to the end."""
    folder = Path(folder)
    count = 0
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d.lower() not in SYSTEM_FOLDERS)
        for name in sorted(names):
            p = Path(root) / name
            if name.startswith(".") or p.is_symlink() or not p.is_file():
                continue
            count += 1
            if count > MAX_FILES:
                raise FolderTooBig(TOO_BIG)
            yield p.relative_to(folder).as_posix(), p


TOO_BIG = "That folder holds far more than a QuadStick drive does. Pick the QuadStick drive itself."


def read_drive(folder: Path) -> list[dict]:
    """Every file under `folder` as {path, data}: `path` relative and '/'-separated,
    `data` base64 (see `_drive_files` for what is left out)."""
    files, total = [], 0
    for rel, p in _drive_files(folder):
        data = p.read_bytes()
        total += len(data)
        if total > MAX_BYTES:
            raise FolderTooBig(TOO_BIG)
        files.append({"path": rel, "data": base64.b64encode(data).decode("ascii")})
    return files


def list_drive(folder: Path) -> list[dict]:
    """Every file under `folder` as {path, size}: names only, nothing read."""
    return [{"path": rel, "size": p.stat().st_size} for rel, p in _drive_files(folder)]


# ------------------------------------------------------------------ writing profiles
# The profile switch reaches 32 files (MAX_SELECTABLE_FILES in web/src/device/layout.ts).
MAX_PROFILE_FILES = 32
# A profile is a few KB; this only stops something that is plainly not one.
MAX_PROFILE_BYTES = 1024 * 1024
TEMP_PREFIX = ".qsps-"     # a dot-file: the firmware deletes any left behind at boot


class NotWritten(ValueError):
    """Refused before anything on the drive was touched."""


def is_profile_name(name: str) -> bool:
    """A file the QuadStick offers on its profile switch: a top-level `.csv` that is
    not a dot-file and has no `prefs.csv` in its name (the firmware's `scan_files`;
    `profilesOnDrive` in web/src/lib/driveFiles.ts). These are what a replace swaps."""
    low = name.lower()
    return low.endswith(".csv") and not low.startswith(".") and "prefs.csv" not in low


def check_profiles(files: dict[str, bytes]) -> None:
    """Raise NotWritten unless every file is a profile the QuadStick will load under
    that name, and the set is one it can switch between."""
    if not files:
        raise NotWritten("Pick at least one profile to put on the QuadStick.")
    seen: set[str] = set()
    for name, data in files.items():
        if problem := check_csv_filename(name):     # also refuses / \ and a leading dot
            raise NotWritten(f"Not written: {problem}.")
        if not is_profile_name(name):
            raise NotWritten(f"'{name}' has prefs.csv in its name, so the QuadStick would never "
                             "offer it. Rename the profile.")
        if name.lower() in seen:     # FAT: two names that differ only in case are one file
            raise NotWritten(f"Two profiles are called {name.lower()}. Leave one of them out.")
        seen.add(name.lower())
        if len(data) > MAX_PROFILE_BYTES or not data.startswith(b"QuadStick"):
            raise NotWritten(f"{name} is not a QuadStick profile.")
    if len(files) > MAX_PROFILE_FILES:
        raise NotWritten(f"That is {len(files)} profiles; the QuadStick can pick only "
                         f"{MAX_PROFILE_FILES}. Leave some out.")


def _write_synced(path: Path, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
        if IS_MAC:                   # fsync alone leaves it in the drive's own cache
            import fcntl
            try:
                fcntl.fcntl(f.fileno(), fcntl.F_FULLFSYNC)
            except OSError:
                pass


def _flush_folder(root: Path) -> None:
    """Get the renames and deletions out of the computer's cache onto the stick.
    macOS and Linux hold FAT writes back for up to ~30 s otherwise."""
    if IS_WINDOWS:
        return                       # each file was flushed; removable drives write through
    try:
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    os.sync()


def replace_profiles(root: Path, files: dict[str, bytes]) -> dict:
    """Put `files` ({name: bytes}) on the drive at `root` in place of the profiles there
    now. Everything else (prefs.csv, joystick.bin, folders) is left alone. When no new
    file is `default.csv`, the drive's own `default.csv` stays: it is the profile the
    QuadStick boots with.

    Order matters for a stick that is pulled out or full: the new files are written and
    flushed under temporary dot-names first, so a failure there leaves the drive as it
    was. Only then are the old profiles removed and the new ones renamed into place.
    Answers {written, removed, kept_default}."""
    root = Path(root)
    check_profiles(files)
    keep_default = "default.csv" not in {n.lower() for n in files}
    old = sorted(p for p in root.iterdir()
                 if is_profile_name(p.name) and p.is_file() and not p.is_symlink()
                 and not (keep_default and p.name.lower() == "default.csv"))
    kept_default = keep_default and (root / "default.csv").is_file()
    if kept_default and len(files) + 1 > MAX_PROFILE_FILES:
        raise NotWritten(f"With default.csv that is {len(files) + 1} profiles; the QuadStick "
                         f"can pick only {MAX_PROFILE_FILES}. Leave some out.")

    temps: dict[str, Path] = {}
    try:
        for i, (name, data) in enumerate(files.items()):
            tmp = root / f"{TEMP_PREFIX}{i}.tmp"
            temps[name] = tmp
            _write_synced(tmp, data)
    except OSError as e:
        for tmp in temps.values():
            tmp.unlink(missing_ok=True)
        if e.errno == errno.ENOSPC:
            raise NotWritten("There is not enough room on the QuadStick drive. Nothing was "
                             "changed.") from e
        raise NotWritten(f"Could not write to the drive ({e.strerror or e}). Nothing was "
                         "changed. Unplug the QuadStick, plug it back in, and try again.") from e

    # From here on the drive is changing. Removing every old profile first also clears
    # a name that differs only in case (FAT keeps the old spelling on a replace).
    try:
        for p in old:
            p.unlink()
        for name, tmp in temps.items():
            os.replace(tmp, root / name)
            # macOS tags every new file (com.apple.provenance) and keeps the tag on FAT
            # as a `._` file beside it. The firmware deletes dot-files at boot; tidy it now.
            (root / f"._{name}").unlink(missing_ok=True)
    finally:
        for tmp in temps.values():
            tmp.unlink(missing_ok=True)
        _flush_folder(root)
    new = {n.lower() for n in files}
    return {"written": sorted(files),
            "removed": [p.name for p in old if p.name.lower() not in new],
            "kept_default": kept_default}


# ------------------------------------------------------------------ finding the drive
def drive_key(name: str) -> str:
    """'Quad Stick', 'QUADSTICK' and 'quad-stick' are one name."""
    return re.sub(r"[\s_-]+", "", name).casefold()


DEFAULT_NAME = "QuadStick"


def mounted_volumes() -> list[tuple[str, Path]]:
    """(name, top folder) of every drive the computer has mounted. Only names are
    looked at here, so a slow network share is never opened."""
    if IS_WINDOWS:
        return _windows_volumes()
    if SANDBOXED:                          # /Volumes itself may not be listed there
        return mac_native.mounted_volumes()
    roots = [Path("/Volumes")] if IS_MAC else [Path("/media") / _user(), Path("/run/media") / _user()]
    out = []
    for root in roots:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        # "Macintosh HD" is a link to / on macOS: never a QuadStick.
        out += [(n, root / n) for n in names if not n.startswith(".") and not (root / n).is_symlink()]
    return out


def _user() -> str:
    return os.environ.get("USER", "")


def _windows_volumes() -> list[tuple[str, Path]]:
    """Drive letters on removable and fixed disks with their labels. Network drives
    and CD drives are not asked: either can stall for seconds."""
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.SetErrorMode(1)                    # SEM_FAILCRITICALERRORS: no "insert a disk" box
    out, mask = [], k32.GetLogicalDrives()
    for i in range(2, 26):                 # C: to Z:; A: and B: are floppies
        if not mask & (1 << i):
            continue
        root = f"{chr(65 + i)}:\\"
        if k32.GetDriveTypeW(root) not in (2, 3):        # DRIVE_REMOVABLE, DRIVE_FIXED
            continue
        label = ctypes.create_unicode_buffer(261)
        if k32.GetVolumeInformationW(root, label, 261, None, None, None, None, 0):
            out.append((label.value, Path(root)))
    return out


def find_drive(remembered: str | None, volumes: list[tuple[str, Path]]) -> tuple[str, Path] | None:
    """The drive with the remembered name; failing that, one called QuadStick."""
    for wanted in (remembered, DEFAULT_NAME):
        if wanted:
            for name, root in volumes:
                if drive_key(name) == drive_key(wanted) and root.is_dir():
                    return name, root
    return None


def volume_name(folder: Path, volumes: list[tuple[str, Path]]) -> str | None:
    """The name of the drive `folder` is the top of, or None when it is a folder
    inside something else: the drive is remembered by name, so it must be a drive."""
    folder = Path(folder)
    for name, root in volumes:
        if folder == root:                 # WindowsPath compares E:\ and e:/ as one
            return name
    return None


class DesktopApi:
    def __init__(self, exports_dir: Path, origin: str, data_dir: Path | None = None,
                 bookmarks=None):
        self._exports = Path(exports_dir).resolve()
        self._origin = origin.rstrip("/")
        self._memory = Path(data_dir) / "drive.json" if data_dir else None
        # Only in the sandbox: how a drive picked once is opened again (mac_native).
        self._bookmarks = bookmarks if bookmarks is not None else (
            mac_native.Bookmarks() if SANDBOXED else None)

    def reveal(self, path: str) -> None:
        target = Path(path).resolve()
        if self._exports not in target.parents or not target.is_file():
            log.warning("reveal refused: %s", path)
            return
        log.info("reveal %s", target)
        if IS_MAC:
            mac_native.reveal(target)
        elif IS_WINDOWS:
            subprocess.Popen(["explorer", f"/select,{target}"])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])

    # ------------------------------------------------------------- the QuadStick drive
    def _memory_data(self) -> dict:
        try:
            data = json.loads(self._memory.read_text("utf-8")) if self._memory else {}
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _remembered(self) -> str | None:
        name = self._memory_data().get("name")
        return name if isinstance(name, str) and name else None

    def _bookmark(self) -> bytes | None:
        mark = self._memory_data().get("bookmark")
        try:
            return base64.b64decode(mark, validate=True) if isinstance(mark, str) and mark else None
        except (binascii.Error, ValueError):
            return None

    def _remember(self, name: str, bookmark: bytes | None = None) -> None:
        """drive.json: the drive's name, and in the sandbox the bookmark that opens it."""
        if not self._memory:
            return
        want = {"name": name}
        if bookmark is not None:
            want["bookmark"] = base64.b64encode(bookmark).decode("ascii")
        elif self._bookmarks is not None and (old := self._bookmark()) is not None:
            want["bookmark"] = base64.b64encode(old).decode("ascii")
        if want != self._memory_data():
            if name != self._remembered():
                log.info("remembering the QuadStick drive as %r", name)
            self._memory.write_text(json.dumps(want), "utf-8")

    @contextmanager
    def _drive(self):
        """The QuadStick's drive, open for the length of the `with`: (name, root,
        allowed), or None when it is not plugged in. `allowed` is False only in the
        sandbox, for a drive that is plugged in but has not been picked yet."""
        if self._bookmarks is not None and (mark := self._bookmark()):
            with self._bookmarks.open(mark) as opened:
                if opened:
                    root, fresh = opened
                    name = volume_name(root, mounted_volumes()) or root.name
                    self._remember(name, fresh or mark)
                    yield name, root, True
                    return
        hit = find_drive(self._remembered(), mounted_volumes())
        if hit and self._bookmarks is None:
            self._remember(hit[0])
        yield (hit[0], hit[1], self._bookmarks is None) if hit else None

    def quadstick_drive(self) -> dict:
        """What is on the drive now: {found, name, files: [{path, size}]}. Not found,
        `name` is the one being looked for, so the page can say what to plug in. In the
        sandbox, a drive that is plugged in but not yet picked adds `needs_permission`."""
        with self._drive() as hit:
            if not hit:
                return {"found": False, "name": self._remembered() or DEFAULT_NAME, "files": []}
            name, root, allowed = hit
            if not allowed:
                return {"found": False, "name": name, "files": [], "needs_permission": True}
            return {"found": True, "name": name, "files": list_drive(root)}

    def read_quadstick_drive(self) -> list[dict] | None:
        """Every file on the drive, for a backup (see `read_drive`); None when it is
        not plugged in, or not yet picked in the sandbox (the page then asks)."""
        with self._drive() as hit:
            if not hit or not hit[2]:
                return None
            name, root, _ = hit
            log.info("reading the QuadStick drive %r at %s", name, root)
            try:
                return read_drive(root)
            except FolderTooBig:
                raise
            except OSError as e:             # unplugged mid-read, or a drive that will not read
                log.warning("reading %s failed: %s", root, e)
                raise ValueError(f"Could not read the drive {name}. Unplug the QuadStick, plug "
                                 "it back in, and try again.") from e

    def write_quadstick_drive(self, files: list[dict]) -> dict:
        """Put these profiles ([{name, data}], data base64) on the drive in place of the
        ones there now (`replace_profiles`), flushed. Answers as `quadstick_drive`. A
        refusal raises: pywebview rejects the JavaScript promise with the message."""
        try:
            decoded = {}
            for f in files:
                name = str(f["name"])
                if name in decoded:
                    raise NotWritten(f"{name} is in the list twice.")
                decoded[name] = base64.b64decode(f["data"], validate=True)
        except (KeyError, TypeError, ValueError) as e:
            if isinstance(e, NotWritten):
                raise
            raise NotWritten("The profiles did not arrive whole. Nothing was changed.") from e
        with self._drive() as hit:
            if not hit:
                raise NotWritten("The QuadStick is not plugged in. Nothing was changed.")
            name, root, allowed = hit
            if not allowed:
                raise NotWritten(f"Press Choose the drive… and pick {name} once, so the app may "
                                 "use it. Nothing was changed.")
            log.info("replacing the profiles on %r at %s with %s", name, root, sorted(decoded))
            try:
                done = replace_profiles(root, decoded)
            except NotWritten:
                raise
            except OSError as e:
                log.warning("writing %s failed part way: %s", root, e)
                raise ValueError(f"Writing to {name} stopped part way ({e.strerror or e}). "
                                 "Restore the backup the app just took if the QuadStick "
                                 "misbehaves.") from e
        log.info("wrote %s, removed %s", done["written"], done["removed"])
        return self.quadstick_drive()

    def choose_quadstick_drive(self) -> dict | None:
        """Ask which drive is the QuadStick, remember it, and answer as
        `quadstick_drive`; None when the dialog is cancelled. A folder that is not the
        top of a drive, or has no profile on it, raises: pywebview rejects the
        JavaScript promise with the message. The dialog opens on the drive when one is
        plugged in, so Open is all it takes; in the sandbox that one pick is what lets
        the app open the drive from then on."""
        import webview
        with self._drive() as hit:
            start = str(hit[1]) if hit else ("/Volumes" if IS_MAC else "")
        picked = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER, directory=start)
        if not picked:
            return None
        folder = Path(picked[0] if isinstance(picked, (list, tuple)) else picked)
        name = volume_name(folder, mounted_volumes())
        if name is None:
            raise ValueError("Pick the QuadStick drive itself, not a folder inside it.")
        if not any(p.suffix.lower() == ".csv" for p in folder.iterdir() if p.is_file()):
            raise ValueError(f"{name} has no profiles on it. Pick the QuadStick drive.")
        if self._bookmarks is not None:
            try:
                self._remember(name, self._bookmarks.create(folder))
            except OSError as e:
                log.warning("no bookmark for %s: %s", folder, e)
                raise ValueError(f"macOS would not let the app keep using {name}. Choose it "
                                 "again.") from e
        else:
            self._remember(name)
        return self.quadstick_drive()

    def open_external(self, url: str) -> None:
        if not url.startswith(self._origin + "/"):
            log.warning("open_external refused: %s", url)
            return
        log.info("open_external %s", url)
        if IS_MAC:
            mac_native.open_url(url)         # no osascript child: the sandbox stops it
        else:
            webbrowser.open(url)
