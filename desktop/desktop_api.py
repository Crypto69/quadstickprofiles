"""What the web app may ask the desktop shell to do (window.pywebview.api).

Two calls, both narrow on purpose: reveal a file the API wrote into the exports
folder, and open one of this app's own URLs in the system browser (that is where
printing happens; a WebView has no print dialog and cannot open tabs)."""
import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

log = logging.getLogger("desktop.api")


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
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        elif os.name == "nt":
            subprocess.Popen(["explorer", f"/select,{target}"])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])

    def open_external(self, url: str) -> None:
        if not url.startswith(self._origin + "/"):
            log.warning("open_external refused: %s", url)
            return
        log.info("open_external %s", url)
        webbrowser.open(url)
