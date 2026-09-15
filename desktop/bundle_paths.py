"""Where the bundled read-only data lives.

Frozen (PyInstaller one-folder): everything the spec lists under `datas` is unpacked
next to the executable, reachable through sys._MEIPASS. From a checkout
(`python desktop/launcher.py`): the same names map onto the repo layout."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# bundle name -> path in the checkout
DEV_MAP = {
    "web_dist": REPO / "web" / "dist",
    "fixtures": REPO / "fixtures",
    "actions": REPO / "actions",
    "alembic": REPO / "api" / "alembic",
    "version.txt": REPO / "desktop" / "version.txt",
}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource_path(name: str) -> Path:
    if is_frozen():
        return Path(sys._MEIPASS) / name          # type: ignore[attr-defined]
    return DEV_MAP[name]
