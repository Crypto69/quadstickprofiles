"""Stage 0 additions.

profiles.firmware   which firmware the profile is authored for. It decides which
                    emulation modes hide the flash drive (catalog.HIDDEN_DRIVE_MODES
                    is {2373: {5,6,7}, 1476: {3,5,7}}), so the warning cannot be
                    hard-coded. Default 2373 — the owner's device.

mappings.kind       'mapping' | 'preference'. A preference row is a per-mode
                    preference override: column A is a preference key, B is empty and
                    C is the value (docs/file-format.md). Before this migration such a
                    row was silently dropped on import, because the table could only
                    hold an output.
mappings.pref_key   the preference key, for kind='preference' only. It gets its own
                    column rather than reusing `output` so that `mappings.output` can
                    keep its FK to output_catalog for every ordinary mapping.
mappings.value      the override value; empty for ordinary mappings.

`output` becomes nullable, and a CHECK enforces the two shapes: a mapping has an
output and no pref_key; a preference row has a pref_key and no output.

The emulation-mode CHECK from 0001 is also replaced: it allowed (0,1,2,3,4,5,7) and
rejected 6, but 6 is a real mode (DualShock 4 with no USB drive) and is one of the
drive-hiding modes on firmware 2373 — exactly the case the warning exists for.

Revision ID: 0002_firmware_and_mapping_kind
Revises: 0001_initial
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_firmware_and_mapping_kind"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


EMULATION_MODES = "(0,1,2,3,4,5,6,7)"
# catalog.FIRMWARE_VERSIONS; kept literal so the migration never drifts with the code
FIRMWARE_VERSIONS = "(2373,1476)"


def upgrade():
    op.add_column("profiles", sa.Column("firmware", sa.Integer, nullable=False, server_default="2373"))
    op.drop_constraint("ck_profiles_emulation_mode", "profiles", type_="check")
    op.create_check_constraint("ck_profiles_emulation_mode", "profiles",
                               f"emulation_mode is null or emulation_mode in {EMULATION_MODES}")
    op.create_check_constraint("ck_profiles_firmware", "profiles", f"firmware in {FIRMWARE_VERSIONS}")
    op.add_column("mappings", sa.Column("kind", sa.Text, nullable=False, server_default="mapping"))
    op.add_column("mappings", sa.Column("pref_key", sa.Text))
    op.add_column("mappings", sa.Column("value", sa.Text, nullable=False, server_default=""))
    op.alter_column("mappings", "output", existing_type=sa.Text, nullable=True)
    op.create_check_constraint("ck_mappings_kind", "mappings", "kind in ('mapping','preference')")
    op.create_check_constraint(
        "ck_mappings_shape", "mappings",
        "(kind = 'mapping'    and output is not null and pref_key is null) or "
        "(kind = 'preference' and output is     null and pref_key is not null)")
    op.create_index("ix_mappings_kind", "mappings", ["kind"])


def downgrade():
    op.drop_constraint("ck_profiles_firmware", "profiles", type_="check")
    op.execute("update profiles set emulation_mode = null where emulation_mode = 6")
    op.drop_constraint("ck_profiles_emulation_mode", "profiles", type_="check")
    op.create_check_constraint("ck_profiles_emulation_mode", "profiles",
                               "emulation_mode is null or emulation_mode in (0,1,2,3,4,5,7)")
    op.drop_index("ix_mappings_kind", table_name="mappings")
    op.execute("delete from mappings where kind = 'preference'")   # cannot be represented
    op.drop_constraint("ck_mappings_shape", "mappings", type_="check")
    op.drop_constraint("ck_mappings_kind", "mappings", type_="check")
    op.alter_column("mappings", "output", existing_type=sa.Text, nullable=False)
    op.drop_column("mappings", "value")
    op.drop_column("mappings", "pref_key")
    op.drop_column("mappings", "kind")
    op.drop_column("profiles", "firmware")
