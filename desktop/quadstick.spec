# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the desktop build. One-folder (fast start, fewer antivirus
# false alarms); build.sh / build.ps1 zip the folder. Run from the repo root:
#   python -m PyInstaller --noconfirm --clean desktop/quadstick.spec \
#       --distpath desktop/dist --workpath desktop/build
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

HERE = Path(SPECPATH).resolve()
ROOT = HERE.parent
NAME = "QuadStick Profile Studio"

# core/ and api/ are editable installs, which PyInstaller's analysis cannot see
# through; point it at the source trees directly.
SRC = [str(ROOT / "core"), str(ROOT / "api")]
for path in SRC:
    if path not in sys.path:
        sys.path.insert(0, path)

datas = collect_data_files("qsprofile")                      # keywords/*.txt, assets/*.webp
datas += [
    (str(ROOT / "web" / "dist"), "web_dist"),
    (str(ROOT / "fixtures"), "fixtures"),
    (str(ROOT / "actions"), "actions"),
    (str(ROOT / "api" / "alembic"), "alembic"),               # env.py + versions/, loaded by path
    (str(HERE / "version.txt"), "."),
]
for dist in ("qsapi", "qsprofile"):                           # /api/version reads qsapi's version
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

hiddenimports = collect_submodules("app") + [
    "sqlalchemy.dialects.sqlite", "sqlalchemy.dialects.sqlite.pysqlite",
    "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.off", "uvicorn.lifespan.on", "uvicorn.logging",
    "pydantic_settings", "openpyxl", "multipart", "python_multipart",
    "alembic.runtime.migration", "alembic.script", "alembic.command",
]
excludes = ["psycopg", "psycopg_binary", "psycopg_pool", "uvloop", "httptools",
            "playwright", "pytest", "tkinter", "_tkinter"]

icon = None
for candidate in ("icons/app.icns" if sys.platform == "darwin" else "icons/app.ico",):
    if (HERE / candidate).is_file():
        icon = str(HERE / candidate)

a = Analysis(
    [str(HERE / "launcher.py")],
    pathex=[str(HERE), *SRC],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NAME,
    console=False,                       # no terminal window; the launcher logs to a file
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=icon,
        bundle_identifier="com.quadstick.profilestudio",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "CFBundleShortVersionString": (HERE / "version.txt").read_text().split("\n")[0].split("=")[-1]
            if (HERE / "version.txt").is_file() else "dev",
        },
    )
