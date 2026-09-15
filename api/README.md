# QuadStick Profile Studio — API

FastAPI + SQLAlchemy 2 + Alembic + Postgres 16, wrapping `core/qsprofile`.
Nothing about the file formats is reimplemented here: parsing, validation,
console conversion, CSV/XLSX writing and the printable card all come from the
core package. This service stores profiles, enforces the catalogs, and
refuses exports while validation errors exist.

## Run with Docker (the NAS path)

```
docker compose up --build -d          # from the repo root
open http://localhost:8000/api/docs   # Swagger UI (everything is under /api)
```

On first start the `api` container waits for Postgres, runs `alembic upgrade
head`, seeds the catalogs from `core/qsprofile/catalog.py`, and imports the
six fixtures with their game-action labels (idempotent; set
`QS_SEED_ON_START=0` to skip). Exported CSVs are also written to the `exports`
volume, to be exposed as an SMB share later. `QS_DB_PASSWORD` and
`QS_API_PORT` can be set in a root `.env` (see `.env.example`).

## Run locally

```
python3.12 -m venv .venv && . .venv/bin/activate
cd core && pip install -e ".[dev]" && cd ../api && pip install -e ".[dev,postgres]"

# a Postgres, e.g. docker run -d --name qs_pg -e POSTGRES_DB=quadstick -e POSTGRES_USER=quadstick \
#      -e POSTGRES_PASSWORD=quadstick -p 5432:5432 postgres:16-alpine
export QS_DATABASE_URL=postgresql+psycopg://quadstick:quadstick@localhost:5432/quadstick
alembic upgrade head
python -m app.seed                    # catalogs + fixtures; --catalog-only to skip fixtures
uvicorn app.main:app --reload
```

Settings (env or `.env`, prefix `QS_`): `DATABASE_URL`, `EXPORTS_DIR`,
`FIXTURES_DIR`, `ACTIONS_DIR`.

## Tests

```
cd api && pytest -q                                   # SQLite, no Docker needed
QS_TEST_DATABASE_URL=postgresql+psycopg://quadstick:quadstick@localhost:55432/quadstick pytest -q
                                                      # same suite through the real Alembic migration
pytest -q                                             # from the repo root: core round-trips + API
```

`tests/test_import_export.py` reuses the byte-identical checks from
`tests/test_roundtrip.py`, through the HTTP import → DB → export path.

**Before every commit that touches `api/`:**

1. `cd api && pytest -q` (SQLite).
2. The same suite against Postgres. It drops and recreates the `public` schema of
   the database it is given, so **never point it at the compose `db` service**;
   start a throwaway one:
   ```
   docker run -d --name qs-test-pg -p 55432:5432 -e POSTGRES_USER=quadstick \
       -e POSTGRES_PASSWORD=quadstick -e POSTGRES_DB=quadstick postgres:16
   QS_TEST_DATABASE_URL=postgresql+psycopg://quadstick:quadstick@localhost:55432/quadstick pytest -q
   docker rm -f qs-test-pg
   ```
   SQLite enforces the CHECKs in `models.py` but has no regex CHECK, no foreign-key
   enforcement and no Alembic run, which is how the 0001 emulation-mode bug and a
   too-long 0004 revision id got through.
3. For a new migration, `alembic upgrade head`, `alembic downgrade -1`, `alembic
   upgrade head` against that container (`QS_DATABASE_URL` pointing at it), and
   exercise any data step with a row or two.
4. `pytest -q` from the repo root, so the core round-trip tests stay green.

## Endpoints

| method | path | notes |
|---|---|---|
| GET | `/api/catalog` | inputs (with jack, incl. legacy names), outputs (PS glyph + Xbox name), functions, tube order, `DIGITAL_JACKS`, `XBOX_TO_PS`, regex families, the 61 `PREFERENCES`, `MODE_OVERRIDABLE`, `EMULATION_MODES`, `HIDDEN_DRIVE_MODES`, `LEGACY_INPUTS`, firmware versions and the format `limits` |
| GET | `/api/profiles?q=&validate=` | library list; `validate=true` adds error/warning/info counts |
| POST | `/api/profiles` | create from JSON (modes, mappings, preferences, game actions, input names) |
| GET / PUT / PATCH / DELETE | `/api/profiles/{id}` | PUT replaces the whole document; PATCH is metadata, `firmware`, `input_names`, `game_actions` |
| POST | `/api/profiles/import` | multipart `file` (.xlsx or .csv), optional `game`, `name`, `firmware`; returns profile + import-time findings |
| GET | `/api/profiles/{id}/validate` | findings + `budget` + `consequence` per severity + `unused_inputs`; the drive-hiding warning uses `HIDDEN_DRIVE_MODES[firmware]` |
| POST | `/api/profiles/validate` | the same, for an **unsaved** document — the editor's live checks, writes nothing |
| POST | `/api/profiles/{id}/duplicate?name=&csv_filename=` | copy, including per-mode override rows; defaults the filename to `<stem>_copy.csv` |
| GET | `/api/profiles/{id}/export.csv?filename=` | device CSV, byte-identical to the add-on; **409** with findings while errors exist |
| GET | `/api/profiles/{id}/export.xlsx` | template-layout workbook; same 409 rule |
| POST | `/api/profiles/{id}/convert` | `{target, name?, csv_filename?}` → new profile + notes + suggested filename |
| GET | `/api/profiles/{id}/card.html` | printable card; game actions, input names (e.g. `lip` → "Chin switch") and per-mode overrides applied |
| GET | `/api/health`, `/health` | liveness; `/health` stays unprefixed for the container health check |

Every output / input / function in a write body is checked against the
catalog and rejected with 422 otherwise. Outputs are stored under PlayStation
names; the profile's `console` picks the header and names at export. The full
`kb_*` / `ir_*` keyword lists are seeded from the catalog; a name outside them
that still matches the family regex is added to `output_catalog` on first use so
the foreign key holds. Function parameters are stored as given: a `2.5`, a `five`,
one parameter too many, `repeat 0` or anything above `MAX_FUNCTION_PARAM` is a core
finding that blocks export, not a schema rejection, so a file the import stored can
always be saved and live-checked from the editor (only an unknown function name, a
comma / line break / non-ASCII cell and the `csv_filename` rule are 422s).

## Schema notes (vs `docs/data-model.md`)

- `input_names (profile_id, input, name)` — per-profile display names for inputs.
- `input_catalog.jack`, `*.sort_order` — physical jack from `DIGITAL_JACKS`; stable dropdown order.
- `profiles.format_version` — the CSV header token (`Version 1.4`), so exports stay byte-identical.
- Postgres regex CHECKs live in the migration; the API enforces the same with Pydantic so SQLite tests behave identically.
- **No `emulation_mode` or `channel` column** (migration 0004, decision D1 of the code
  review): the device reads the emulation mode from the `enable_DS3_emulation` row of
  the profile's Preferences block (or a per-mode override row, or `prefs.csv`) and the
  channel from each mode's C3, so `preferences` and `modes.channel` are the only places
  the app keeps them. `ProfileSummary.emulation_mode` is still on the wire, **derived**
  from that row, so the Library can warn about a drive-hiding mode. 0004 also replaces
  `ck_profiles_csv_filename` with `catalog.CSV_FILENAME_RE` (case-insensitive: the app
  accepts mixed case, the device lowercases) and appends a note to `notes` where a
  profile carried an app-only emulation mode, since that value never reached the file.
  The upgrade stops, naming the rows, if a stored `csv_filename` breaks the device rule.
- **Column B as read** (migration 0005): `mappings.function` is nullable — NULL is an
  empty function cell, which the device reads as `normal` but which must export as
  empty — and an override row keeps whatever its column B said in `mappings.column_b`
  (the device ignores it; the bytes must round-trip). On the wire `function` is `""`
  for either; a mapping row posted without `function` means `normal`, and an
  override row posted without one has an empty B. The bridge stores what the parser
  gave and substitutes nothing; only the card treats an empty cell as normal.

## Stage 0 additions (firmware knowledge)

- **`profiles.firmware`** (migration 0002, default 2373 — the owner's device). Which
  emulation modes hide the flash drive depends on it:
  `catalog.HIDDEN_DRIVE_MODES = {2373: {1,3,5,6,7}, 1476: {3,5,7}}` (2373 is the
  union of the QCM code and its docs until modes 1 and 3 are verified on the
  owner's device). The warning is generated from that table by core's `validate`,
  never hard-coded; the API passes the profile's firmware in.
- **Per-mode preference override rows** (`mappings.kind = 'preference'`, with
  `pref_key` and `value`). Before 0002 such a row was silently dropped on import.
  `output` is now nullable and a CHECK enforces the two row shapes; `output` keeps
  its FK to `output_catalog` for ordinary mappings. On the wire the key travels in
  `output` with `kind: "preference"`, matching the file layout. Unverified on a
  device, so the validator warns on every one.
- **Legacy input names** (`push`, `right_sip_long`, `right_puff_long`,
  `bluetooth_status`) are seeded into `input_catalog` with `kind='legacy'`, so a
  profile that uses one satisfies the FK and gets a warning instead of a 422.
- **Validate response** carries `budget` (rows used/free per mode, unused inputs,
  preference-row capacity for the firmware), `consequence` — what the device
  actually does, per severity present — and `unused_inputs` (free in every mode).
- **`POST /api/profiles/validate`** validates an unsaved document, so the editor's
  live checks never write to the database.
