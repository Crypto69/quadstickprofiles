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

## Signing

- **macOS**: the release build is signed with the owner's Developer ID and
  notarised by Apple, so it opens like any other app. `build.sh` signs whenever a
  "Developer ID Application" identity is in the keychain (`sign.sh`: every Mach-O
  file, hardened runtime, `entitlements.plist` — the two exceptions CPython needs
  under the hardened runtime), and release.yml then runs `notarize.sh`. Both
  scripts work from a checkout too; their headers show how.

  `sign.sh` resolves the identity to exactly one certificate and passes `codesign`
  its SHA-1 hash, because a name that matches two (a Developer ID Application and
  a Developer ID Installer, say) makes `codesign` fail as "ambiguous". Set
  `CODESIGN_IDENTITY` to a full name, a unique substring, or the 40-character hash
  from `security find-identity -v -p codesigning` if you have more than one; with
  no match, or more than one, `sign.sh` lists what it found and stops.

  The workflow reads **five** repository secrets — `MACOS_CERT_P12` (the
  certificate exported as .p12, base64), `MACOS_CERT_PASSWORD`, and for
  notarisation an App Store Connect API key: `APPLE_API_KEY_ID`,
  `APPLE_API_ISSUER_ID`, `APPLE_API_KEY_P8` (the .p8, base64). It is all five or
  none: with none it builds unsigned, so a fork still gets a build; with some of
  them it fails the job immediately rather than shipping a half-signed app, since
  a signed but un-notarised Developer ID app is still blocked by Gatekeeper. The
  release notes only claim "signed and notarised" when `notarize.sh` actually
  succeeded, and otherwise carry the right-click → *Open* instructions.

  Changing the bundle identifier after a signed release makes macOS treat it as a
  different app, so it stays `ai.myaccessibility.quadstickprofilestudio`.
- **Windows**: unsigned. SmartScreen shows "Windows protected your PC" the first
  time. Click *More info* → *Run anyway*. The app needs the WebView2 runtime, which
  Windows 11 and up-to-date Windows 10 already have; without it the app opens in
  your default browser instead and tells you so. Runtime download:
  <https://developer.microsoft.com/microsoft-edge/webview2/>.
- An unsigned macOS build (no identity in the keychain) hits Gatekeeper: right-click
  → *Open* once, or `xattr -dr com.apple.quarantine "QuadStick Profile Studio.app"`.

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
`scripts/desktop_check.sh`. `release.yml` runs it twice: once on the app as built,
so a broken build fails before waiting on Apple, and again on the app *unpacked
from the zip that ships* — after stapling and re-zipping, so what is uploaded is
what was launched.
