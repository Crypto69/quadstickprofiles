"""The emulation mode and the channel come from the file, not from columns.

Decision D1 of the code-review fix plan. The QuadStick reads its USB emulation
mode from the `enable_DS3_emulation` row of a profile's Preferences block (or a
per-mode override row, or prefs.csv) and each mode's connection from that mode's
own C3 cell. `profiles.emulation_mode` and `profiles.channel` never reached the
exported file, so the editor's picker looked live and was not, and the
drive-hiding warning judged a value the device never sees. Both columns go, with
`ck_profiles_emulation_mode`. Where a profile carried an emulation mode, a note
is appended to `notes` saying that app-only value was never exported, so the
owner can add the preference row if the profile needs one.

`ck_profiles_csv_filename` is replaced as well (C5): the 0001 pattern
`^[^,\\s]+\\.csv$` let `../evil.csv` and absolute paths through. The new CHECK is
`catalog.CSV_FILENAME_RE` — letters, digits, `_ - .`, at most 31 characters
including `.csv` — matched case-insensitively, because the app accepts mixed
case at the edge (the device lowercases every name it reads) and SQLite, which
has no regex CHECK, must not accept a row Postgres refuses. The leading-dot and
whitespace rules stay with `catalog.check_csv_filename`, which every write path
applies first. The upgrade stops with a plain message if a stored name breaks
the device rule, rather than renaming a file the device already has. That check
reads rows, so it only runs online; `alembic upgrade --sql` renders the rest.

Revision ID: 0004_emulation_mode_in_the_file
Revises: 0003_templates
Create Date: 2026-09-13
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0004_emulation_mode_in_the_file"
down_revision = "0003_templates"
branch_labels = None
depends_on = None

# catalog.CSV_FILENAME_RE; kept literal so the migration never drifts with the code
CSV_FILENAME_PATTERN = r"^[a-z0-9_\-.]{1,27}\.csv$"
OLD_CSV_FILENAME_PATTERN = r"^[^,\s]+\.csv$"
EMULATION_MODES = "(0,1,2,3,4,5,6,7)"

NEVER_EXPORTED = ("Emulation mode {mode} was set in this app only and was never written to the "
                  "exported file. The QuadStick applies the enable_DS3_emulation row of the "
                  "Preferences block (or prefs.csv); add that row if this profile needs it.")


def upgrade():
    if not context.is_offline_mode():          # a query with a result: nothing to render offline
        bad = op.get_bind().execute(sa.text(f"select id, csv_filename from profiles "
                                            f"where csv_filename !~* '{CSV_FILENAME_PATTERN}'")).all()
        if bad:
            names = ", ".join(f"{pid}: '{name}'" for pid, name in bad)
            raise RuntimeError("These profiles have a csv_filename the QuadStick cannot load; rename "
                               f"them (PATCH /api/profiles/{{id}}) and run the upgrade again: {names}")
    # the note text is built per row from the column that is about to go
    op.execute(sa.text(
        "update profiles set notes = coalesce(notes || chr(10) || chr(10), '') || :head "
        "|| cast(emulation_mode as text) || :tail where emulation_mode is not null"
    ).bindparams(head=NEVER_EXPORTED.split("{mode}")[0], tail=NEVER_EXPORTED.split("{mode}")[1]))
    op.drop_constraint("ck_profiles_emulation_mode", "profiles", type_="check")
    op.drop_column("profiles", "emulation_mode")
    op.drop_column("profiles", "channel")
    op.drop_constraint("ck_profiles_csv_filename", "profiles", type_="check")
    op.create_check_constraint("ck_profiles_csv_filename", "profiles",
                               f"csv_filename ~* '{CSV_FILENAME_PATTERN}'")


def downgrade():
    op.drop_constraint("ck_profiles_csv_filename", "profiles", type_="check")
    op.create_check_constraint("ck_profiles_csv_filename", "profiles",
                               f"csv_filename ~ '{OLD_CSV_FILENAME_PATTERN}'")
    op.add_column("profiles", sa.Column("channel", sa.Text, nullable=False, server_default="usb"))
    op.add_column("profiles", sa.Column("emulation_mode", sa.SmallInteger))
    op.create_check_constraint("ck_profiles_emulation_mode", "profiles",
                               f"emulation_mode is null or emulation_mode in {EMULATION_MODES}")
    # best effort: the file's own values, where they fit the old columns
    op.execute("update profiles set emulation_mode = cast(p.value as smallint) from preferences p "
               "where p.profile_id = profiles.id and p.scope = 'profile' "
               "and p.key = 'enable_DS3_emulation' and p.value ~ '^[0-7]$'")
    op.execute("update profiles set channel = m.channel from modes m "
               "where m.profile_id = profiles.id and m.position = 1 and m.channel in ('usb','bluetooth')")
