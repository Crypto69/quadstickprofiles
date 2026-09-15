# Data model (Postgres)

Mirrors `core/qsprofile/model.py`. Outputs are stored canonically (PlayStation
names); the console is a property of the profile, applied on export.

Two things are deliberately **not** profile columns (decision D1, 2026-09-13): the
USB emulation mode and the connection channel. The device reads the emulation mode
from the `enable_DS3_emulation` row of the profile's `Preferences` block (the
`preferences` table, `scope = 'profile'`, or a per-mode override row), and the
channel from each mode's own C3 (`modes.channel`). Earlier schemas carried
`profiles.emulation_mode` and `profiles.channel`; neither ever reached the exported
file, so the editor's picker looked live and was not, and the drive-hiding warning
checked a value the device never sees. Migration 0004 drops both.

```sql
create table profiles (
  id            bigserial primary key,
  name          text not null,                 -- sheet title / display name
  csv_filename  text not null                 -- catalog.CSV_FILENAME_RE (migration 0004);
                check (csv_filename ~* '^[a-z0-9_\-.]{1,27}\.csv$'),  -- the app applies the
                                               -- full catalog.check_csv_filename rule first
  game          text,                          -- "Fortnite"
  console       text not null default 'playstation' check (console in ('playstation','xbox')),
  firmware      int not null default 2373      -- catalog.FIRMWARE_VERSIONS; decides which
                check (firmware in (2373,1476)),   -- emulation modes hide the flash drive
  notes         text,
  source_url    text,                          -- Google Sheet URL if imported
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

create table modes (
  id          bigserial primary key,
  profile_id  bigint not null references profiles on delete cascade,
  position    smallint not null check (position between 1 and 16),  -- = mode number
  name        text not null,                   -- tab name ("Sprint")
  label       text not null,                   -- C1 ("Left joy")
  channel     text not null default 'usb',     -- C3: none | usb | bluetooth | both (2373)
  unique (profile_id, position)
);

create table mappings (
  id          bigserial primary key,
  mode_id     bigint not null references modes on delete cascade,
  row_order   int not null,
  kind        text not null default 'mapping' check (kind in ('mapping','preference')),
  output      text references output_catalog(name),   -- null on a preference row
  pref_key    text,                            -- the preference key, kind='preference' only
  value       text not null default '',         -- the override value, kind='preference' only
  function    text references function_catalog(name),  -- NULL = empty cell (device reads normal); NULL on override rows (0005)
  column_b    text,                            -- an override row's column B, verbatim; the firmware ignores it (0005)
  params      jsonb not null default '[]',     -- [5, 2000]
  comment     text,                            -- never exported
  unique (mode_id, row_order),
  -- the two row shapes: a mapping has an output, a per-mode preference override
  -- has a key and a value (docs/file-format.md). Keeping the key out of `output`
  -- lets `output` keep its foreign key for every ordinary mapping.
  check ((kind = 'mapping'    and output is not null and pref_key is null) or
         (kind = 'preference' and output is     null and pref_key is not null))
);

create table mapping_inputs (                  -- ordered inputs, columns C..J
  mapping_id  bigint not null references mappings on delete cascade,
  seq         smallint not null check (seq between 0 and 7),
  input       text not null references input_catalog(name),
  primary key (mapping_id, seq)
);

create table preferences (                     -- global < profile < mode precedence
  id          bigserial primary key,
  scope       text not null check (scope in ('global','profile','mode')),
  profile_id  bigint references profiles on delete cascade,
  mode_id     bigint references modes on delete cascade,
  key         text not null,
  value       text not null
);

create table game_actions (                    -- output -> what it does in a game
  id          bigserial primary key,
  profile_id  bigint references profiles on delete cascade,   -- null = shared game template
  game        text not null,
  mode_name   text,                            -- null = applies to every mode
  output      text not null,
  action      text not null
);

-- Catalogs, seeded from core/qsprofile/catalog.py. These drive every dropdown and
-- every validation rule, so the UI can never produce a keyword the device rejects.
create table input_catalog   (name text primary key, kind text, tube text, action text, strength text, label text);
create table output_catalog  (name text primary key, grp text, ps_glyph text, xbox_name text, xbox_glyph text, label text);
create table function_catalog(name text primary key, max_params smallint, description text);
```

Seeding: iterate `catalog.all_mouthpiece_inputs()`, the side/lip/joystick/digital
lists, `catalog.OUTPUTS`, `catalog.XBOX_TO_PS`, `catalog.FUNCTIONS`. Keyboard
(`kb_*`) and IR (`ir_*`) outputs are regex families in the catalog; seed the
common ones explicitly and keep the regex as the fallback validator.

## Implemented additions (api/alembic/versions/0001_initial.py)

- `input_names (profile_id, input, name)` — per-profile display names for
  inputs, e.g. `lip` → "Chin switch"; fed to `render()` as `actions["inputs"]`.
- `input_catalog.jack` and `sort_order` on every catalog — `DIGITAL_JACKS`
  from `catalog.py`, and a stable dropdown order.
- `profiles.format_version` (default `Version 1.4`) — the CSV header token,
  kept so a re-export is byte-identical.
- Regex-family outputs (`kb_*`, `ir_*`) that pass the catalog regex are inserted
  into `output_catalog` on first use so the `mappings.output` foreign key holds.
- `input_catalog` also holds the four older input names in `catalog.LEGACY_INPUTS`
  with `kind = 'legacy'`, so a profile that still uses one satisfies the
  `mapping_inputs.input` foreign key and gets a warning rather than a rejection.
- `mappings.kind` / `pref_key` / `value` and `profiles.firmware` arrive in
  migration `0002_firmware_and_mapping_kind`, which also widens the
  emulation-mode CHECK to include **6** (DualShock 4 with no USB drive) —
  `0001_initial` wrongly rejected it, and it is one of the drive-hiding modes
  on firmware 2373.
- `profiles.is_template` arrives in `0003_templates`.
- Migration `0004` (code review, decision D1)
  drops `profiles.emulation_mode`, `profiles.channel` and
  `ck_profiles_emulation_mode`, and replaces `ck_profiles_csv_filename`'s
  `^[^,\s]+\.csv$` — which let `../evil.csv` and absolute paths through — with
  `catalog.CSV_FILENAME_RE`. The lowercase-only regex is the device's view (it
  lowercases every name); the app accepts mixed case at the edge and the
  validator says what the device will call the file. Where a profile carried an
  app-only `emulation_mode`, the data step appends a note to `notes` saying that
  value was never exported. The downgrade re-adds both columns. `ProfileSummary`
  keeps an `emulation_mode` field on the wire, now **derived** from the
  profile-scope `enable_DS3_emulation` row, so the Library's drive-hiding warning
  still works. Run the API suite against Postgres (`QS_TEST_DATABASE_URL`) and
  check 0004 up/down/up before trusting it: the regex CHECK only exists there
  (it is `~*`: the app accepts mixed case at the edge).
- Migration `0005_column_b_as_read` makes `mappings.function` nullable with no
  server default (NULL is an empty function cell, which core keeps as `""` so
  `x,,lip,` round-trips) and adds `mappings.column_b` for an override row's
  column B. `ck_mappings_shape` gains: a mapping row has no `column_b`, an
  override row has no `function`. Existing override rows' dummy `normal` becomes
  NULL. The downgrade puts `normal` back and drops `column_b`.
