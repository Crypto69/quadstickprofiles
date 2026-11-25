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
check and CI do this so they never touch a real profile). A relative folder is under
`~`.

The Mac App Store build runs in Apple's App Sandbox, where `~` is the app's container:
the data and the log are under
`~/Library/Containers/ai.myaccessibility.quadstickprofilestudio/Data/Library/…`, and
exports go to `~/Downloads/QuadStick exports` (the one folder outside the container
it may write without asking). See "Mac App Store" below.

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
  `sh desktop/set_github_secrets.sh` loads all five from a local folder
  (`~/Desktop/qs-signing` by default, see the script header for the file names)
  without printing any of them; delete the folder afterwards.

  Changing the bundle identifier after a signed release makes macOS treat it as a
  different app, so it stays `ai.myaccessibility.quadstickprofilestudio`.
- **Windows**: unsigned. SmartScreen shows "Windows protected your PC" the first
  time. Click *More info* → *Run anyway*. The app needs the WebView2 runtime, which
  Windows 11 and up-to-date Windows 10 already have; without it the app opens in
  your default browser instead and tells you so. Runtime download:
  <https://developer.microsoft.com/microsoft-edge/webview2/>.
- An unsigned macOS build (no identity in the keychain) hits Gatekeeper: right-click
  → *Open* once, or `xattr -dr com.apple.quarantine "QuadStick Profile Studio.app"`.

## Mac App Store

The same app, signed differently: App Sandbox on (`mas.entitlements.plist`, each
permission explained there), no hardened runtime, the store's provisioning profile
inside, packed as an installer `.pkg`. The Developer ID download above is not
sandboxed and does not change.

What the sandbox changes, all in `mac_native.py`:

- **The QuadStick's drive.** The app still sees the drive by name, but may not open
  it until the person picks it once with *Choose the drive…* (the dialog opens on the
  drive; pressing *Open* is enough). The app keeps a security-scoped bookmark of it
  in `drive.json` and opens the drive through it from then on, after a replug and
  after a restart. Until then the device page says the drive is plugged in and asks
  for that one pick (`needs_permission`). A different stick is a different drive and
  is picked once too.
- **Exports** go to `~/Downloads/QuadStick exports`; *Show in folder* works there.
- No `osascript` or `open`: Finder, the browser and message boxes go through AppKit
  (both builds).

```sh
sh desktop/build_mas.sh --sandbox-test        # ad hoc signed, the same sandbox, runs here
sh scripts/desktop_check.sh --sandboxed "desktop/dist/QuadStick Profile Studio.app/Contents/MacOS/QuadStick Profile Studio"
"desktop/dist/QuadStick Profile Studio.app/Contents/MacOS/QuadStick Profile Studio" --drive-check
sh desktop/build_mas.sh ~/Downloads/QuadStick_Profile_Studio_Mac_App_Store.provisionprofile
sh desktop/upload_mas.sh desktop/dist/QuadStickProfileStudio-<version>-mas.pkg   # or Apple's Transporter app
```

`--drive-check` prints which drives the app can see and open, and what the device
page would be told, without changing anything; inside the sandbox an unpicked drive
shows as `false` / `needs_permission`. A store-signed app does not start outside the
store, so test with `--sandbox-test` (or TestFlight).

What the store build needs, once (the owner's Apple account):

1. The App ID `ai.myaccessibility.quadstickprofilestudio` (registered) and the app
   in App Store Connect (My Apps → + → New App, that bundle ID).
2. Certificates in the keychain: **Apple Distribution** (signs the app) and **Mac
   Installer Distribution** (signs the `.pkg`). Xcode → Settings → Accounts → Manage
   Certificates → +.
3. A **Mac App Store Connect** provisioning profile for that App ID with the Apple
   Distribution certificate, downloaded. `sign_mas.sh` checks it is the store one, for
   this app, from the certificate's team, and not expired.
4. To upload, the App Store Connect API key needs the App Manager role.

`.github/workflows/store-mac.yml` builds and runs the sandbox check on every change
to this, and on tags. With the four store secrets as well as the three API ones it
also signs, packs and has Apple check the `.pkg` (left on the run's page); *Run
workflow* with *upload* ticked sends it to App Store Connect. `sh
desktop/set_mas_secrets.sh` loads the four from a folder (file names in its header).
Submitting the build for review stays by hand in App Store Connect.

The build number (`CFBundleVersion`) is the commit count, so it grows with every
upload; the version is `scripts/version.sh`'s. Upload only tagged versions: an
untagged `1.105` would sort above a later tag `1.21`.

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
10. Plug in the QuadStick. *The device* → *On the QuadStick* says "Reading the drive
    Quad Stick now" and lists its profiles within a few seconds; unplug it and the list
    falls back to the newest backup. *Back up the QuadStick* reads the drive with no
    dialog and says "Backed up N files". With no QuadStick plugged in, *Choose the
    drive…* takes any drive with a `.csv` on top and is remembered (`drive.json` in the
    data folder). *Restore a backup…* → *Save the backup
    (.zip)* writes the zip to `QuadStick exports` and reveals it.
    *Put my profiles on the QuadStick…* (enabled only while the drive is found): tick
    two profiles, press *Back up, then put 2 profiles on*. A new backup appears, the
    list shows the two (plus the drive's own `default.csv` when neither is one),
    `prefs.csv` is still on the drive, and after a replug the QuadStick loads them. On
    macOS, ejecting afterwards gives no "not ejected properly" warning.
    **Mac App Store build** (`build_mas.sh --sandbox-test`, from a fresh container):
    the page first says the drive is plugged in and asks to choose it; *Choose the
    drive…* → *Open* lists it; quit, replug, relaunch: it is listed with no dialog.
11. *Test it* → *Open the tester in your browser* opens `/tester` in the system browser.
    In Chrome or Edge, with a QuadStick plugged in, *Connect the QuadStick* lists it.

The automated part of this (`--headless`, curl `/`, `/api/version`, an export) is
`scripts/desktop_check.sh`. `release.yml` runs it twice: once on the app as built,
so a broken build fails before waiting on Apple, and again on the app *unpacked
from the zip that ships* — after stapling and re-zipping, so what is uploaded is
what was launched.
