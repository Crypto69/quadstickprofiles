<p align="center">
  <img src="desktop/icons/logo-source.png" alt="QuadStick Profile Studio" width="420">
</p>

<p align="center">
  <a href="https://github.com/Crypto69/quadstickprofiles/actions/workflows/ci.yml"><img src="https://github.com/Crypto69/quadstickprofiles/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

A self-hosted app for QuadStick game profiles: read them, check them against what the
device will actually accept, convert between PlayStation and Xbox button names, and
print a reference card. Runs as a desktop app, or on a NAS in Docker. Copying the
`.csv` onto the QuadStick's flash drive stays manual on purpose — the app walks you
through it.

## Why I built this

I recently received my QuadStick with the amazing help of David Nelson from
<http://www.innovativeat.com.au/>, who helps supply adaptive gaming equipment to
people across Australia. Getting my head around how it worked, including how
profiles and modes worked, was quite difficult at first.

I started playing with the profiles but that spreadsheet was driving me crazy. It
just wasn't clear enough, so I figured I needed to teach myself how the whole
thing worked. I built myself a quick app that allows me to configure things much
faster now. This also allowed me to teach myself a lot more about how it all
works.

Hopefully, it helps you. If it does, drop me a message. I'm very open to feedback
and changes, so let me know if there's something else you want.

## What it can do

The screenshots below are a real profile — my own Call of Duty: WWII setup, six modes.

### Your profile library

Everything you've imported, in one list. Each row says how many modes it has, which
button names it uses, what it's called on the device, and whether it will load
cleanly. Import the `.xlsx` you downloaded from the Google Sheet or a `.csv` copied
straight off the QuadStick — nothing is uploaded anywhere, it all runs on your own
machine.

![The profile library](docs/screenshots/01-library.webp)

- Start a new profile blank, or from a bundled starter (Fortnite, Call of Duty, and more).
- Search by game or name.
- Duplicate, rename, delete, or convert a profile to the other console's button names.
- A validation badge on every row, and a warning when a profile's emulation mode would
  hide the flash drive on that firmware.

### The device is the way in

The main editor is a photo of the real QuadStick. Every part is clickable: the three
mouthpiece holes, the side tube, the lip button, the joystick, the four jacks on the
back. Beside it, the whole mode laid out as a grid — sip and puff, soft and hard,
holes on their own and in combination.

![The device view](docs/screenshots/02-device-view.webp)

Point at a part and it lights up, along with everywhere its mappings live. Click it
and the page narrows to just that part, with a way back out.

![One part selected](docs/screenshots/03-device-part-selected.webp)

### Rows, when you want the detail

The raw rows, with the spreadsheet row numbers you'd see in the Google Sheet. Output,
how it behaves, input, and your own note — each function parameter labelled the way
the firmware actually reads it. Rows nothing triggers can be folded away.

![The rows view](docs/screenshots/04-rows.webp)

### Mode map

Every mode, with an arrow for each way to get between them, labelled with the input
that does it. Any mode you can't get out of gets flagged.

![The mode map](docs/screenshots/05-mode-map.webp)

### Settings, in plain language

Name, game, on-device filename, PlayStation or Xbox naming, firmware, how it pretends
to be a controller, USB or Bluetooth. Each one explains what it does and what happens
if you leave it alone.

![Profile settings](docs/screenshots/06-settings.webp)

### It tells you what's wrong — and what isn't

Live checks on every edit: filename rules, mode and row limits, unknown inputs and
outputs, function parameter counts, characters that would corrupt the file, preference
keys and values, threshold ordering, emulation modes that hide the drive.

Things to fix are kept separate from things that are simply true about your profile. A
chin press that fires an action *and* changes mode is a design, not a fault — so it
goes under "What this profile does", not "Problems".

![Findings, split into problems and notes](docs/screenshots/12-findings.webp)

Errors block export. Warnings and notes don't. Click any finding and it jumps you to
the mode and view where it lives.

### Getting it onto the QuadStick

Export a `.csv` that is byte-identical to what the official add-on produces — then a
five-step checklist you can tick off, including the LED counting rule for picking the
file on the device.

![The export checklist](docs/screenshots/11-export-checklist.webp)

### Printing

Print to PDF from your browser, or onto paper. Everything is sized to stay readable
from across the room.

**Detailed sheets** — an orientation page, then one page per mode:

![Print: orientation page](docs/screenshots/09a-print-orientation.webp)

Each button carries its own label: the action for the game, and underneath it your own
note from the Note column. Rows the game's action list doesn't cover — "Resupply from
teamate", "Med" — are labelled by your note alone.

![Print: one mode page](docs/screenshots/09-print-mode-page.webp)

**Summary** — every command once, with dots for the modes it works in, then a compact
table per mode to tape next to the monitor:

![Print: the summary sheet](docs/screenshots/10-print-summary.webp)

### The QuadStick's own settings

Import, edit and export the device's `prefs.csv`: all 61 settings, grouped and
searchable, with the fiddly ones folded away and the right control for each. It says
plainly which one wins: the device, then the profile, then the mode.

![Device settings](docs/screenshots/07-device-settings.webp)

### Learn how it actually works

Nine short pages — the three parts of a row, files vs modes vs rows, reading the
lights, soft vs hard, how an output can behave, patterns from real profiles — with
animations showing what you do next to what the console sees.

![How it works](docs/screenshots/08-learn.webp)

### Built to be usable

- Single-pointer: nothing needs you to hold one control while operating another. No
  dragging, no sliders.
- Full keyboard navigation with a clear focus ring, 44px targets, WCAG 2.1 AA clean.
- Respects reduced-motion. Fonts bundled, so it works fully offline with no
  third-party requests.

### Running it

- Desktop app: one zip for Windows or macOS, no Docker needed.
- Or Docker on a NAS. Or the `qsprofile` command line for checking, converting and
  rendering cards.

---

## How the repo is laid out

Start with `docs/INSTALL.md` to run it, or `docs/file-format.md` to understand
what a QuadStick profile actually is.

```
docs/                install and deploy guides, verified file formats, data model, hardware
docs/screenshots/    the images used in this README
core/qsprofile/      tested Python core (parse · validate · convert · render)
api/                 FastAPI + SQLAlchemy + Alembic over the core (api/README.md)
web/                 Vue 3 + Vite + TypeScript front end (web/README.md)
tests/               round-trip tests (pytest)
fixtures/            real profiles from the owner (xlsx from Google Sheets, csv off the device)
actions/             output → game-action labels (Fortnite, Call of Duty)
samples/             rendered cards (PDF) and a converted CSV to try on the device
```

## Install it

No NAS? `docs/INSTALL.md` covers the desktop app (a zip for Windows or macOS, no
Docker) and prebuilt Docker images, both from the
[Releases page](https://github.com/Crypto69/quadstickprofiles/releases).

## Run the whole thing

```
docker compose up --build -d
open http://localhost:8324          # the app
open http://localhost:8325/api/docs # Swagger
```

Three containers: `web` (nginx serving the built SPA, proxying `/api`), `api` and
`db`. On first start the API migrates, seeds the catalogs from
`core/qsprofile/catalog.py`, and imports the fixtures. Ports and the database
password come from a root `.env` (see `.env.example`).

## Work on it

```
python3.12 -m venv .venv && . .venv/bin/activate
cd core && pip install -e ".[dev]" && cd ../api && pip install -e ".[dev,postgres]" && cd ..
pytest -q                                   # core round-trips + API, on SQLite

cd web && npm install && npm test           # Vitest
npm run dev                                 # localhost:5173, /api proxied to :8000
```

Run the API tests against Postgres before trusting a migration — SQLite enforces
the CHECKs declared in `models.py`, but the regex CHECK on `csv_filename` lives
only in the migration:

```
QS_TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/db pytest -q api/tests
```

## The core on its own

```
qsprofile check   fixtures/ddfortnite.xlsx
qsprofile card    fixtures/ddfortnite.csv actions/actions_fortnite.json card.html
qsprofile convert fixtures/Call_of_Duty_Advanced_Warfare_XBox_One.xlsx playstation out.csv out.csv
```
