"""macOS calls the desktop build makes through AppKit/Foundation (PyObjC, which
pywebview's Cocoa backend already brings), and what changes inside Apple's App
Sandbox, which only the Mac App Store build runs in.

The sandbox is decided by the signature, not by a setting: macOS starts a process in
it when its executable is signed with `com.apple.security.app-sandbox`
(`desktop/mas.entitlements.plist`), and then sets APP_SANDBOX_CONTAINER_ID. Inside it:

- `~` is the app's container (`~/Library/Containers/<bundle id>/Data`), so the data
  folder and the logs move there by themselves. Exports go to the real Downloads
  folder (`real_home()`), the one folder outside the container the entitlements allow
  without asking, so *Show in folder* shows somewhere a person can find again.
- The QuadStick's drive cannot be opened just because it is mounted. The person
  picks it once in a folder dialog; the app keeps a security-scoped bookmark of it
  (`create_bookmark`) and opens the drive through that bookmark from then on
  (`open_bookmark`), every launch, as long as it is the same drive.
- No child processes that talk to other apps: `open -R` and `osascript` are replaced
  by NSWorkspace and NSAlert (`reveal`, `open_url`, `alert`), here for both builds.
- Some files a plain Python reads are outside the sandbox (`quiet_system_files`).

Every function here is safe to call on a Mac without the sandbox; none is imported
on Windows or Linux."""
import os
import pwd
from contextlib import contextmanager
from pathlib import Path

SANDBOXED = bool(os.environ.get("APP_SANDBOX_CONTAINER_ID"))

# NSURL bookmark options (Foundation), as numbers so this module imports even where
# a PyObjC release names them differently.
_CREATE_WITH_SECURITY_SCOPE = 1 << 11
_RESOLVE_WITHOUT_UI = 1 << 8
_RESOLVE_WITHOUT_MOUNTING = 1 << 9
_RESOLVE_WITH_SECURITY_SCOPE = 1 << 10


def real_home() -> Path:
    """The person's own home folder, not the sandbox container `~` points at."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def quiet_system_files() -> None:
    """Inside the sandbox `mimetypes` would read /etc/apache2/mime.types, which exists
    but may not be opened, and fail with PermissionError on first use (it only skips
    files that are missing). Python's own table knows every type this app serves."""
    import mimetypes
    mimetypes.knownfiles[:] = []         # init(files=[]) would still add them
    mimetypes.init()


# ------------------------------------------------------------------- AppKit calls
def reveal(path: Path) -> None:
    """Select the file in a Finder window."""
    from AppKit import NSWorkspace
    from Foundation import NSURL
    NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_(
        [NSURL.fileURLWithPath_(str(path))])


def open_url(url: str) -> bool:
    """Open a web address in the default browser."""
    from AppKit import NSWorkspace
    from Foundation import NSURL
    return bool(NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url)))


def alert(title: str, text: str) -> None:
    """A message box before any window exists. Main thread only."""
    from AppKit import NSAlert, NSApplication
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    box = NSAlert.alloc().init()
    box.setMessageText_(title)
    box.setInformativeText_(text)
    box.addButtonWithTitle_("OK")
    box.runModal()


def mounted_volumes() -> list[tuple[str, Path]]:
    """(name, top folder) of every mounted drive under /Volumes, from NSFileManager,
    which answers inside the sandbox too. Only names are asked for."""
    from Foundation import NSFileManager
    skip_hidden = 1 << 1                       # NSVolumeEnumerationSkipHiddenVolumes
    urls = NSFileManager.defaultManager().mountedVolumeURLsIncludingResourceValuesForKeys_options_(
        None, skip_hidden) or []
    out = []
    for url in urls:
        p = Path(str(url.path()))
        if p.parent == Path("/Volumes") and not p.name.startswith("."):
            out.append((p.name, p))
    return sorted(out)


# -------------------------------------------------------------- security-scoped bookmarks
def create_bookmark(folder: Path) -> bytes:
    """A bookmark of `folder` the app may open again on a later launch. Only works for
    a folder the person picked in a dialog this session (or one already opened through
    a bookmark). Raises OSError when macOS refuses."""
    from Foundation import NSURL
    url = NSURL.fileURLWithPath_isDirectory_(str(folder), True)
    data, err = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
        _CREATE_WITH_SECURITY_SCOPE, None, None, None)
    if data is None:
        raise OSError(f"macOS would not keep permission for {folder}: {err}")
    return bytes(data)


@contextmanager
def open_bookmark(bookmark: bytes):
    """Open the folder a bookmark points at, for as long as the `with` lasts. Yields
    (path, fresh) where `fresh` is a new bookmark to keep in place of the old one when
    macOS says it is out of date, else None. Yields None when the folder is not there
    (the drive is unplugged) or macOS no longer allows it; it never mounts or asks."""
    from Foundation import NSURL, NSData
    data = NSData.dataWithBytes_length_(bookmark, len(bookmark))
    url, stale, _err = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
        data, _RESOLVE_WITH_SECURITY_SCOPE | _RESOLVE_WITHOUT_UI | _RESOLVE_WITHOUT_MOUNTING,
        None, None, None)
    if url is None:
        yield None
        return
    started = bool(url.startAccessingSecurityScopedResource())
    try:
        path = Path(str(url.path()))
        if not started or not path.is_dir():
            yield None
            return
        fresh = None
        if stale:
            try:
                fresh = create_bookmark(path)
            except OSError:
                fresh = None
        yield path, fresh
    finally:
        if started:
            url.stopAccessingSecurityScopedResource()


class Bookmarks:
    """What DesktopApi needs from the sandbox, as one object a test can replace."""
    create = staticmethod(create_bookmark)
    open = staticmethod(open_bookmark)
