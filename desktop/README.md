# Desktop build

QuadStick Profile Studio as a normal app for a Windows or macOS laptop: no Docker,
no Postgres, no NAS. One process runs the API on a free `127.0.0.1` port, serves the
built web app itself (`api/app/spa.py`), keeps the data in a SQLite file, and shows
the whole thing in a native window (pywebview: WebView2 on Windows, WKWebView on
macOS).

## Where things live

| What | Windows | macOS |
|---|---|---|
| database `studio.sqlite`, `launcher.lock`, WebView storage | `%LOCALAPPDATA%\QuadStick Profile Studio` | `~/Library/Application Support/QuadStick Profile Studio` |
| `launcher.log` | `%LOCALAPPDATA%\QuadStick Profile Studio\Logs` | `~/Library/Logs/QuadStick Profile Studio` |
| exported `.csv` / `.xlsx` | `Documents\QuadStick exports` | `~/Documents/QuadStick exports` |

Set `QS_DESKTOP_HOME=<folder>` to put all three under one folder instead (the build
check and CI do this so they never touch a real profile).

Upgrading is "replace the app folder". The data folder is never inside it. A newer
build upgrades the database on first launch (`alembic upgrade head` from the stamp
the first launch wrote; see `api/app/standalone.py`).

## Build it

Needs Node 22 and Python 3.12. From the repo root:

```sh
pip install -e core -e api -r desktop/requirements.txt
sh desktop/build.sh                                   # macOS / Linux
powershell -ExecutionPolicy Bypass -File desktop\build.ps1   # Windows
```

Output: `desktop/dist/QuadStickProfileStudio-<version>-<os>-<arch>.zip`. The version
comes from `scripts/version.sh` (a `v*` tag, else `<VERSION>.<commits since>`), and
is written to `desktop/version.txt` for `/api/version`. The build is one folder
(`QuadStick Profile Studio/` on Windows, `QuadStick Profile Studio.app` on macOS),
zipped. `release.yml` runs exactly these scripts on GitHub's runners.

From a checkout, without packing, after `cd web && npm run build`:

```sh
python desktop/launcher.py               # the window
python desktop/launcher.py --headless    # server only; prints the URL
```

## Unsigned, on purpose (for now)

The builds are not code-signed or notarised.

- **Windows**: SmartScreen shows "Windows protected your PC" the first time. Click
  *More info* → *Run anyway*. The app needs the WebView2 runtime, which Windows 11
  and up-to-date Windows 10 already have; without it the app opens in your default
  browser instead and tells you so. Runtime download:
  <https://developer.microsoft.com/microsoft-edge/webview2/>.
- **macOS**: Gatekeeper says the app "cannot be opened because the developer cannot
  be verified". Either right-click → *Open* once, or run
  `xattr -dr com.apple.quarantine "QuadStick Profile Studio.app"` after unzipping.

## Smoke test (do this on every build before a release)

macOS first, then Windows. Delete nothing between steps unless it says so.

1. First launch: the Library shows the six shipped profiles; `launcher.log` says
   `schema: created` and lists the imports.
2. Import `fixtures/ddfortnite.xlsx` through *Import*.
3. Open a profile, change one mapping, save; reopen it and see the change.
4. *Export*: the checklist says "Saved to …/QuadStick exports/…"; *Show in folder*
   reveals the file in Finder / Explorer.
5. *Print detailed sheets* and *Print summary* open in the system browser; the Print
   button there prints.
6. Quit, relaunch: the data is still there; the log says `schema: upgraded`.
7. Unzip a newer build over the old folder (data folder untouched); it launches and
   the log says `schema: upgraded`.
8. Launch a second copy while one is running: a dialog says it is already running.
9. Windows only: no console window appears; on a machine without WebView2 the app
   opens in the browser with a dialog explaining that.

The automated part of this (`--headless`, curl `/`, `/api/version`, an export) is
what `build.sh` checks in CI.
