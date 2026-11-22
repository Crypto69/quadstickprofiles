# Install QuadStick Profile Studio

Three ways to run the same app. Pick the row that matches what you have.

| You have | Use | Where the data lives |
|---|---|---|
| a Windows or macOS laptop, nothing else | **Desktop app** (below) | your user profile; exports in `Documents/QuadStick exports` |
| Docker Desktop (or any Docker) | **Docker anywhere** (below) | a Postgres volume next to the compose file; exports in `./exports` |
| a NAS you administer | `docs/DEPLOY-NAS.md` | the NAS |

Profiles move between any of them as `.xlsx` / `.csv` files: export from one, import
into the other. Copying a `.csv` onto the QuadStick's flash drive stays manual on
purpose; the app walks you through it after every export.

## Desktop app (no Docker)

1. Open the [Releases page](https://github.com/Crypto69/quadstickprofiles/releases)
   and download `QuadStickProfileStudio-<version>-windows-x64.zip` or
   `…-macos-arm64.zip`.
2. Unzip anywhere (Windows: a folder you own, e.g. `Documents\QuadStick Profile Studio`;
   macOS: drag the `.app` to Applications or leave it in Downloads).
3. Open `QuadStick Profile Studio`. The first launch creates the database and loads
   the shipped example profiles.

- **macOS**: the app is signed and notarised by Apple, so it opens like any other app.
- **Windows**: the app is not signed, so Windows asks once: "Windows protected your
  PC" → *More info* → *Run anyway*. It needs the WebView2 runtime, which Windows 11
  and up-to-date Windows 10 already have; without it the app opens in your browser
  instead and says so.

**Upgrade**: unzip the new version over the old folder. Your data is elsewhere (see
`desktop/README.md` for the exact paths) and is upgraded on the next launch.

**Uninstall**: delete the folder; delete the data folder named in `desktop/README.md`
if you want the database gone too.

## Docker anywhere

Needs Docker with Compose (Docker Desktop on Windows/macOS, or Docker Engine).

```sh
mkdir quadstick && cd quadstick
curl -LO https://github.com/Crypto69/quadstickprofiles/releases/latest/download/docker-compose.release.yml
curl -Lo .env https://github.com/Crypto69/quadstickprofiles/releases/latest/download/env.example
#  ^ then edit .env and set QS_DB_PASSWORD before the first start
docker compose -f docker-compose.release.yml up -d
```

Then open <http://localhost:8324>. The images come from GitHub Container Registry
(`ghcr.io/crypto69/quadstick-profile-studio-api` and `-web`, linux/amd64 and
linux/arm64). `APP_VERSION=1.7 docker compose -f docker-compose.release.yml up -d`
pins a release; without it you get `latest`. Ports, the exports folder and the
database location are the `QS_*` variables in `.env` (the comments in it explain them).

**Upgrade**: `docker compose -f docker-compose.release.yml pull && docker compose -f
docker-compose.release.yml up -d`. Migrations run on start.

## Testing the QuadStick (the "Test it" page)

The tester reads the QuadStick straight from the browser, so it has two needs
whichever way you run the app:

- **Chrome or Edge** on the computer the QuadStick is plugged into. Safari and Firefox
  cannot read USB devices.
- **A secure address.** Browsers only allow USB on `https://…` or on this computer's own
  `localhost`.

| You run | Open the tester |
|---|---|
| Desktop app | Press **Open the tester in your browser** on the Test it page. It opens the same app in your browser at a `localhost` address. If that browser is Safari or Firefox, copy the address into Chrome or Edge. |
| Docker on this computer | <http://localhost:8324/tester> in Chrome or Edge. |
| Docker on another machine, or a NAS | Its `https://` address. `docs/DEPLOY-NAS.md` → "HTTPS over Tailscale" sets one up in two commands. Over plain `http://` the page explains why it cannot connect. |

The page gives you the small `qstest.csv` profile it needs, with the steps to copy it
onto the QuadStick.

Backing up the QuadStick's drive (the **QuadStick backup** box on the Profiles page)
works in any browser and over plain `http://`.

## From source

`README.md` → "Work on it". `docker compose up --build -d` at the repo root builds
the same images locally.
