"""QuadStick Profile Studio, desktop edition.

One process: FastAPI on a free localhost port (serving the built web app and the
API, on a SQLite file in the user's data folder) plus a pywebview window pointed
at it. The smoke test is in README.md here.

    python desktop/launcher.py              # from a checkout, after `npm run build`
    python desktop/launcher.py --headless   # server only, prints the URL (used by CI
                                            # and the build check; Ctrl+C to stop)
"""
import logging
import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP_NAME = "QuadStick Profile Studio"
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:               # so bundle_paths / desktop_api import when frozen
    sys.path.insert(0, str(HERE))

from host_os import IS_MAC, IS_WINDOWS      # noqa: E402  (needs HERE on sys.path when frozen)

log = logging.getLogger("desktop")


# ----------------------------------------------------------------- folders, logging
def user_folders():
    """Per-OS locations. QS_DESKTOP_HOME=<dir> puts everything under one folder
    instead (the build check and CI use it, so they never touch a real profile)."""
    override = os.environ.get("QS_DESKTOP_HOME")
    if override:
        base = Path(override)
        data, logs, exports = base / "data", base / "logs", base / "exports"
    else:
        import platformdirs
        data = Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))
        logs = Path(platformdirs.user_log_dir(APP_NAME, appauthor=False))
        exports = Path.home() / "Documents" / "QuadStick exports"
    for d in (data, logs, exports):
        d.mkdir(parents=True, exist_ok=True)
    return data, logs, exports


def setup_logging(log_file: Path):
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.stdout is None or sys.stderr is None:      # windowed build: no console at all
        stream = open(log_file, "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = stream
    else:
        logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))


def apply_version(version_file: Path):
    """desktop/version.txt, written by build.sh / build.ps1, feeds /api/version."""
    try:
        for line in version_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key in ("APP_VERSION", "GIT_SHA", "BUILD_TIME") and value:
                os.environ.setdefault(f"QS_{key}", value.strip())
    except FileNotFoundError:
        pass


# --------------------------------------------------------------- single instance
class SingleInstance:
    """A lock on a file in the data folder; the OS releases it when we die."""

    def __init__(self, path: Path):
        self.path = path
        self.fh = None

    def acquire(self) -> bool:
        self.fh = open(self.path, "a+")
        try:
            if IS_WINDOWS:
                import msvcrt
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


def native_message(title: str, text: str):
    """A message the user can see when there is no window yet."""
    try:
        if IS_WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)   # MB_ICONINFORMATION
        elif IS_MAC:
            import subprocess
            subprocess.run(["osascript", "-e",
                            f'display dialog "{text}" with title "{title}" buttons {{"OK"}}'])
        else:
            print(f"{title}: {text}")
    except Exception:                                    # never let a dialog crash the launcher
        print(f"{title}: {text}")


# ------------------------------------------------------------------------ server
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(app, port: int):
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None,
                            loop="asyncio", http="h11", ws="none", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    return server, thread


def wait_for(url: str, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"the server did not answer at {url} within {timeout:.0f}s")


# ------------------------------------------------------------------------ window
def open_window(url: str, api, storage: Path) -> str:
    """Returns how the app was shown: 'window' or 'browser' (WebView missing)."""
    try:
        import webview
        webview.create_window(APP_NAME, url, js_api=api, width=1280, height=860,
                              min_size=(900, 600), text_select=True)
        webview.start(private_mode=False, storage_path=str(storage))
        return "window"
    except Exception as e:                               # no WebView2 runtime, or a GUI error
        log.exception("could not open the app window: %s", e)
        import webbrowser
        webbrowser.open(url)
        native_message(APP_NAME,
                       "The app window could not be opened, so it was opened in your browser "
                       "instead. Press OK when you are done with it to stop the app.")
        return "browser"


# -------------------------------------------------------------------------- main
def main(argv=None) -> int:
    multiprocessing.freeze_support()
    argv = sys.argv[1:] if argv is None else argv
    headless = "--headless" in argv

    from bundle_paths import resource_path
    data, logs, exports = user_folders()
    setup_logging(logs / "launcher.log")
    log.info("starting; data=%s exports=%s", data, exports)

    os.environ.setdefault("QS_DATABASE_URL", f"sqlite+pysqlite:///{data / 'studio.sqlite'}")
    os.environ["QS_EXPORTS_DIR"] = str(exports)
    os.environ["QS_FIXTURES_DIR"] = str(resource_path("fixtures"))
    os.environ["QS_ACTIONS_DIR"] = str(resource_path("actions"))
    os.environ["QS_STATIC_DIR"] = str(resource_path("web_dist"))
    os.environ["QS_NO_DOTENV"] = "1"
    apply_version(resource_path("version.txt"))

    lock = SingleInstance(data / "launcher.lock")
    if not lock.acquire():
        log.info("another instance holds the lock; exiting")
        native_message(APP_NAME, f"{APP_NAME} is already running.")
        return 0

    # Only now: settings and the engine are built when app.* is first imported.
    from app.db import engine
    from app.standalone import prepare_schema
    from app.seed import main as seed
    from app.main import app
    from desktop_api import DesktopApi

    log.info("schema: %s", prepare_schema(engine, resource_path("alembic")))
    seed([])

    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    server, thread = start_server(app, port)
    wait_for(f"{origin}/health")
    log.info("serving at %s", origin)

    if headless:
        print(f"QuadStick Profile Studio is at {origin}/ (Ctrl+C to stop)", flush=True)
        try:
            while thread.is_alive():
                thread.join(0.5)
        except KeyboardInterrupt:
            pass
    else:
        open_window(f"{origin}/", DesktopApi(exports, origin), data / "webview")

    log.info("window closed; stopping the server")
    server.should_exit = True
    thread.join(10)
    os._exit(0)                                          # do not wait on stray keep-alives


if __name__ == "__main__":
    sys.exit(main())
