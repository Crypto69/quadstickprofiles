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

The builds are not code-signed, so expect one prompt:

- **Windows**: "Windows protected your PC" → *More info* → *Run anyway*. Needs the
  WebView2 runtime, present on Windows 11 and up-to-date Windows 10; without it the
  app opens in your browser instead and says so.
- **macOS**: "cannot be opened because the developer cannot be verified" →
  right-click the app → *Open*, once.

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

## From source

`README.md` → "Work on it". `docker compose up --build -d` at the repo root builds
the same images locally.
