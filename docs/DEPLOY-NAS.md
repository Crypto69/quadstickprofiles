# Deploying QuadStick Profile Studio on a NAS — step by step

Runs the app as three Docker containers on a home NAS, reachable from any
browser on your LAN (and optionally over Tailscale). Written against a
TOS 6 NAS; the Docker steps are the same on Synology, QNAP or any Linux
box — only the "TOS" notes are specific to that platform.

The three containers:

| container | does |
|---|---|
| `web` | nginx serving the built SPA, proxying `/api` to `api` |
| `api` | FastAPI, wraps `core/qsprofile` — import, validate, export, card |
| `db` | Postgres 16 — the profiles live here |

Placeholders used throughout:

| Placeholder | Meaning | Example |
|---|---|---|
| `<your-nas>` | the NAS hostname or LAN IP | `nas.local`, `192.0.2.10` |
| `<vol>` | the storage volume you deploy onto | `/Volume1`, `/volume2` |

## The short version

If you have done this before, the whole deployment is:

```sh
cd <vol>               # your storage volume; each app gets a subdirectory
docker run --rm -v <vol>:/w -w /w -e HOME=/tmp alpine/git \
  clone https://github.com/Crypto69/quadstickprofiles.git quadstick
cd quadstick && chmod -R a+rX . && chmod +x deploy.sh api/entrypoint.sh
cp .env.example .env   # set QS_DB_PASSWORD; the rest can stay as-is
./deploy.sh --no-pull  # build and start; later runs: ./deploy.sh
```

Then open `http://<your-nas>:8324` and check `curl http://<your-nas>:8324/api/version`.
The database lives in `data/pg` inside the checkout, so it sits on the same
volume you cloned onto. The numbered steps below explain each line, and cover
the exports share, backups, Tailscale and troubleshooting.

## Step 1 — Check the hardware

- **Prebuilt images exist** for people without a NAS (`docs/INSTALL.md`,
  `docker-compose.release.yml`), but the NAS keeps building from source with
  `deploy.sh`: the checkout is the deployment, and `/api/version` reports its commit.
- **Any x86_64 or ARM64 NAS.** Nothing here is CPU-heavy: the images are
  `python:3.12-slim`, `nginx:alpine` and `postgres:16` (Debian, on purpose — see the comment in `docker-compose.yml`), all of which
  publish both architectures. There is no CAD or mesh stack.
- **RAM** — 2 GB is plenty. Postgres and a FastAPI worker are the whole load.
- **Disk** — a few hundred MB of images, plus the database and `exports/`,
  which hold kilobytes per profile.

## Step 2 — Prepare the NAS (one-time)

On TOS 6:

1. **App Center → install Docker** ("DockerEngine"). Confirm over SSH:
   `docker compose version`.
2. **Git is not installed and does not need to be.** `which git` prints
   nothing on this box; even the App Center package only gives interactive
   shells an alias that scripts cannot call. Every git operation here runs
   in a throwaway `alpine/git` container instead.
3. **Pick the storage volume your apps live on** — `<vol>` from here on.
   Give each app its own subdirectory directly under it, so this one becomes
   `<vol>/quadstick`. Confirm the volume exists: `ls -d <vol>`.

   You do not need to create data folders by hand. The database, backups
   and exports live *inside the checkout* (`./data/pg`, `./data/backups`,
   `./exports`), so cloning onto that volume puts the data there too.
   `deploy.sh` creates them with the right ownership.
4. **Enable SSH** (Control Panel → Terminal & SNMP) and log in as an admin
   user. Consider moving SSH off port 22 while you are there.

On another NAS: install Docker (with Compose v2), create a folder, enable SSH.

## Step 3 — Clone the repository

**There is no `git` on this NAS.** `which git` prints nothing: TOS exposes it
only as a shell alias that scripts — and the first clone — cannot use. Borrow
one from a throwaway container instead. This is the same trick `deploy.sh`
uses for every later pull.

```bash
cd <vol>
docker run --rm -v <vol>:/w -w /w -e HOME=/tmp alpine/git \
  clone https://github.com/Crypto69/quadstickprofiles.git quadstick
cd quadstick
chmod -R a+rX .                     # TOS shares strip file modes on checkout
chmod +x deploy.sh api/entrypoint.sh
```

The container runs as root, so the checkout is root-owned. That is fine —
`deploy.sh` is run as root over SSH anyway — but it is why the `chmod` lines
come straight after.

The repository is **public**, so this needs no deploy key, token or login. A
private repo would prompt for a username and fail with
`could not read Username for 'https://github.com'`.

Clone onto that volume and everything follows — this is the whole reason the
data paths are relative. `data/` and `exports/` are gitignored.

### Ports

| Port | Used by |
|---|---|
| 8324 | the app (LAN) |
| 8325 | the API direct, for `/api/docs` |
| 8444 | optional Tailscale HTTPS front |

These are the defaults, so a fresh clone needs no port editing. The first
deploy of this app failed with `address already in use` because 8080 was
taken by something else — if 8324 clashes on your box, change `QS_WEB_PORT`
in `.env`. Keep a note of what each of your apps uses; a NAS runs out of
memorable ports faster than you expect.

## Step 4 — Write `.env`

`deploy.sh` refuses to run without it, because a missing `.env` silently
deploys Postgres with the default password.

```bash
cp .env.example .env
vi .env
```

| variable | what it does |
|---|---|
| `QS_DB_PASSWORD` | Postgres password. **Change it.** |
| `QS_WEB_PORT` | the app itself (default `8324`) |
| `QS_API_PORT` | the API direct, for Swagger at `/api/docs` (default `8325`) |
| `QS_EXPORTS_HOST` | *optional* — move exports out of `./exports` |
| `QS_BACKUP_HOST` | *optional* — move backups out of `./data/backups` |
| `QS_PGDATA_HOST` | *optional* — move the database out of `./data/pg` |

**In practice you only set `QS_DB_PASSWORD`.** The three `_HOST` variables
are commented out on purpose: left unset, the data lands inside the checkout
on Volume 5, which is what you want.

Set one only to move data elsewhere — most usefully exports, into a folder
inside a TOS share so they show up over SMB:

```sh
QS_EXPORTS_HOST=<vol>/shared/quadstick-exports    # mkdir -p it first
```

If you do, create the folder **before** the first start, or Docker creates it
root-owned and the container cannot write to it.

`QS_PGDATA_HOST` is a set-once decision. Changing it later points Postgres at
an empty directory and the app comes up with no profiles — the old ones are
still in the old folder, but moving them across means a dump and restore
(Step 8).

## Step 5 — Build and start it

```bash
./deploy.sh --no-pull
```

First build takes a few minutes (npm install for the SPA, pip for the API).
On start the `api` container waits for Postgres, runs `alembic upgrade head`,
seeds the catalogs from `core/qsprofile/catalog.py`, and imports the
fixtures — three as starter profiles, the rest as ordinary ones. It is
idempotent, so restarts do not duplicate anything. `QS_SEED_ON_START=0`
skips it.

Open `http://<your-nas>:8324`. The Library page listing the seeded profiles
is the acceptance test.

## Step 6 — Update to a new version

```bash
cd <vol>/quadstick
./deploy.sh              # pulls main, fixes share file modes, builds, restarts
./deploy.sh --no-pull    # rebuild what is checked out, without pulling
./deploy.sh --force      # deploy even if an export was just written
```

`deploy.sh` stamps both images with a readable deploy number and the commit
it built. The number is shown top-right in the app's header and answers "did
my deploy land?" without reading a commit hash:

```bash
curl http://<your-nas>:8324/api/version
# {"version":"0.2.0","app_version":"1.3","commit":"f5bf601","built":"2026-09-12T18:40Z"}
```

The number is `<VERSION file>.<commits since that file last changed>`, so every
deployed commit gets the next minor (1.0, 1.1, 1.2 …) automatically. To start
a new line, change the `VERSION` file in the repo root to `2` and commit: the
next deploy is 2.0. A local dev build shows `dev`.

Migrations run on start. They are forward-only in practice, but each one has
a working `downgrade` and the chain has been tested up → down → up on
Postgres 16.

If the project's git history was ever rewritten upstream (force-push), a
plain pull refuses. Reset once, then deploy as usual:

```bash
git fetch origin && git reset --hard origin/main && ./deploy.sh --no-pull
```

## Step 7 — The exports share

Every CSV or XLSX the app exports is also written into `exports/`. With
`QS_EXPORTS_HOST` pointed into a share, the workflow from any machine on the
LAN is: export in the app → open the share → copy the file onto the
QuadStick's flash drive. That last step stays manual on purpose, and the app
walks through it after every export.

## Step 8 — Backups

The database holds the profiles; fixtures and catalogs are re-seeded from the
repo, so a backup is only the profile data. Dumps land in
`<vol>/quadstick/data/backups`. One line, verified to restore:

```bash
docker compose exec -T db sh -c \
  'pg_dump -U quadstick quadstick | gzip > /backups/quadstick-$(date +%F).sql.gz'
```

As a nightly cron on the NAS:

```cron
15 3 * * * cd <vol>/quadstick && docker compose exec -T db sh -c 'pg_dump -U quadstick quadstick | gzip > /backups/quadstick-$(date +\%F).sql.gz' && find <vol>/quadstick/data/backups -name '*.sql.gz' -mtime +30 -delete
```

(`%` needs escaping in a crontab.) To restore into a fresh database:

```bash
docker compose exec -T db psql -U quadstick -d postgres -c 'create database restored;'
docker compose exec -T db sh -c 'gunzip -c /backups/quadstick-2026-09-12.sql.gz | psql -U quadstick -d restored -q'
```

Checked on a real dump: 6 profiles (3 of them starters) and 1215 mapping rows
came back, including the per-mode preference override rows.

## Step 9 — HTTPS over Tailscale (optional)

If the NAS is on your tailnet, Tailscale can front the app with HTTPS without
opening anything to the internet:

```bash
tailscale serve --bg --https=8444 http://127.0.0.1:8324
tailscale serve status
```

The app is then at `https://<your-nas>.<your-tailnet>.ts.net:8444`. Use a
port other than 443 if something else already serves it. The app has no
login: anyone on your LAN or tailnet can use it, which is the intended scope.

## Step 10 — Run the test suite on the NAS (optional)

Tests are not baked into the images. Mount them from the checkout:

```bash
docker compose run --rm -v "$PWD/tests:/app/tests:ro" \
  api sh -c 'pip install -q pytest && python -m pytest -q /app/tests /app/api/tests'
```

Run the API tests **against Postgres**, not SQLite — SQLite does not enforce
the CHECK constraints, and that is how the 0001 emulation-mode bug got
through:

```bash
docker compose exec -T api sh -c \
  'QS_TEST_DATABASE_URL=postgresql+psycopg://quadstick:$QS_DB_PASSWORD@db:5432/quadstick \
   python -m pytest -q /app/api/tests'
```

## Health checks

Both `db` and `api` have health checks, and `web` waits for `api` to be
healthy, so a slow first start does not leave nginx serving a broken page.
`/health` is deliberately left unprefixed (as well as `/api/health`) for
exactly this.

nginx resolves the `api` upstream **per request** through Docker's DNS at
127.0.0.11, rather than once at startup. This matters: nginx normally refuses
to start at all if an upstream name does not resolve, so a slow `api`
container would otherwise take the `web` container down with it.

## Is it working?

```bash
curl http://<your-nas>:8324/api/health      # {"status":"ok"}
curl http://<your-nas>:8324/api/version     # commit + build time
curl http://<your-nas>:8324/api/profiles    # the library
docker compose ps                             # all three up, db and api healthy
```

## After a reboot

`restart: unless-stopped` brings all three containers back by themselves,
`web` waiting on a healthy `api`. Check `docker compose ps`; if you use the
Tailscale front, run `tailscale serve status` and repeat the `serve` command
if its entry is gone.

## TOS 6 notes

- **Underscores, not hyphens**, in service and volume names — TOS's bundled
  docker-compose chokes on hyphens. The compose file already follows this.
- **App Center installs onto whichever volume TOS chose**, which is not
  necessarily the one you deploy into. Find them rather than assuming:
  `ls -d /Volume*/@apps/DockerEngine /Volume*/@apps/git 2>/dev/null`.
- **Docker CLI** lives under `<vol>/@apps/DockerEngine/dockerd/bin`; add it
  to `PATH` in `~/.bashrc`. If the daemon is down, start **DockerEngine** in
  App Center and the containers come back.
- **git** installed from App Center is at `<vol>/@apps/git/bin/git`, and
  interactive shells may only see it as an alias that scripts cannot use —
  `deploy.sh` probes the usual locations, reads `.git/HEAD` itself and pulls
  through an `alpine/git` container when needed.
- **Share ACLs strip file modes** on clone/pull: run `chmod -R a+rX .` in the
  repo directory afterwards (`deploy.sh` does this for you, and re-marks
  `deploy.sh` and `api/entrypoint.sh` executable).
- **SSH auto-block**: a burst of SSH connections can blacklist your client IP
  (ping works, SSH times out). Unblock under Control Panel → Security, or
  connect from your other address (LAN vs tailnet).
- Docker's disk fills up quietly. `docker system df` shows the damage and
  `docker system prune -af --volumes` clears it — but read what it will delete
  first, because it removes volumes of stopped containers from *other*
  projects too.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `git clone` → `could not read Username for 'https://github.com'` | Either there is no git (use the `alpine/git` container in Step 3), or the repo went private again. Check: `curl -s -o /dev/null -w '%{http_code}' https://github.com/Crypto69/quadstickprofiles` — 200 is public. |
| `which git` prints nothing | Expected. Nothing to fix — Step 3 and `deploy.sh` both use the container. |
| `deploy.sh` exits with ".env is missing" | Copy it: `cp .env.example .env`, then set `QS_DB_PASSWORD`. |
| `deploy.sh` refuses: "an export was written in the last minute" | Someone is mid-download. Wait a minute, or `./deploy.sh --force`. |
| Build fails in `npm ci` / `pip` with a timeout | Mirror hiccup — rerun `./deploy.sh --no-pull`. |
| `/api/version` shows the old commit | The build cache served a stale layer — `docker compose build --no-cache api`. |
| `api` stuck unhealthy, logs mention alembic | A migration failed. `docker compose logs api`; fix and redeploy. Do not delete `pg_data` unless you have a backup. |
| UI loads but every API call 404s | Stale `web` image — `docker compose build --no-cache web`. |
| `web` exits at startup, "host not found in upstream" | The nginx config lost its per-request resolver. Rebuild `web` from a clean checkout. |
| Exports fail, folder is root-owned | You set `QS_EXPORTS_HOST` to a folder that did not exist, so Docker made it as root. Stop, `chown` it to your user, start again. |
| Port already in use | Change `QS_WEB_PORT` in `.env` (and the `tailscale serve` target). |
| Profiles vanished after a rebuild | `data/pg` was deleted, or `QS_PGDATA_HOST` changed. Restore from a backup (Step 8). |
| `db` will not start, logs mention permissions on PGDATA | Something widened the modes on `data/pg`; Postgres refuses a group/world-readable data directory. `chmod 700 data/pg`. `deploy.sh` skips `data/` when it fixes TOS modes, so this should not recur. |
