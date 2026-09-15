"""Initial schema: catalogs, profiles, modes, mappings, inputs, preferences,
game actions, per-profile input names. From docs/data-model.md.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "input_catalog",
        sa.Column("name", sa.Text, primary_key=True),
        sa.Column("kind", sa.Text), sa.Column("tube", sa.Text), sa.Column("action", sa.Text),
        sa.Column("strength", sa.Text), sa.Column("label", sa.Text), sa.Column("jack", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "output_catalog",
        sa.Column("name", sa.Text, primary_key=True),
        sa.Column("grp", sa.Text), sa.Column("ps_glyph", sa.Text), sa.Column("xbox_name", sa.Text),
        sa.Column("xbox_glyph", sa.Text), sa.Column("label", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "function_catalog",
        sa.Column("name", sa.Text, primary_key=True),
        sa.Column("max_params", sa.SmallInteger), sa.Column("description", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "profiles",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("csv_filename", sa.Text, nullable=False),
        sa.Column("game", sa.Text),
        sa.Column("console", sa.Text, nullable=False, server_default="playstation"),
        sa.Column("channel", sa.Text, nullable=False, server_default="usb"),
        sa.Column("emulation_mode", sa.SmallInteger),
        sa.Column("notes", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Column("format_version", sa.Text, nullable=False, server_default="Version 1.4"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("console in ('playstation','xbox')", name="ck_profiles_console"),
        sa.CheckConstraint(r"csv_filename ~ '^[^,\s]+\.csv$'", name="ck_profiles_csv_filename"),
        sa.CheckConstraint("emulation_mode is null or emulation_mode in (0,1,2,3,4,5,7)",
                           name="ck_profiles_emulation_mode"),
    )
    op.create_table(
        "modes",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("profile_id", sa.BigInteger, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("channel", sa.Text, nullable=False, server_default="usb"),
        sa.UniqueConstraint("profile_id", "position", name="uq_modes_profile_position"),
        sa.CheckConstraint("position between 1 and 16", name="ck_modes_position"),
    )
    op.create_index("ix_modes_profile_id", "modes", ["profile_id"])
    op.create_table(
        "mappings",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("mode_id", sa.BigInteger, sa.ForeignKey("modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_order", sa.Integer, nullable=False),
        sa.Column("output", sa.Text, sa.ForeignKey("output_catalog.name"), nullable=False),
        sa.Column("function", sa.Text, sa.ForeignKey("function_catalog.name"), nullable=False,
                  server_default="normal"),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("comment", sa.Text),
        sa.UniqueConstraint("mode_id", "row_order", name="uq_mappings_mode_row"),
    )
    op.create_index("ix_mappings_mode_id", "mappings", ["mode_id"])
    op.create_table(
        "mapping_inputs",
        sa.Column("mapping_id", sa.BigInteger, sa.ForeignKey("mappings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("seq", sa.SmallInteger, primary_key=True),
        sa.Column("input", sa.Text, sa.ForeignKey("input_catalog.name"), nullable=False),
        sa.CheckConstraint("seq between 0 and 7", name="ck_mapping_inputs_seq"),
    )
    op.create_table(
        "preferences",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("profile_id", sa.BigInteger, sa.ForeignKey("profiles.id", ondelete="CASCADE")),
        sa.Column("mode_id", sa.BigInteger, sa.ForeignKey("modes.id", ondelete="CASCADE")),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.CheckConstraint("scope in ('global','profile','mode')", name="ck_preferences_scope"),
    )
    op.create_index("ix_preferences_profile_id", "preferences", ["profile_id"])
    op.create_table(
        "game_actions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("profile_id", sa.BigInteger, sa.ForeignKey("profiles.id", ondelete="CASCADE")),
        sa.Column("game", sa.Text, nullable=False),
        sa.Column("mode_name", sa.Text),
        sa.Column("output", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
    )
    op.create_index("ix_game_actions_profile_id", "game_actions", ["profile_id"])
    op.create_index("ix_game_actions_game", "game_actions", ["game"])
    op.create_table(
        "input_names",
        sa.Column("profile_id", sa.BigInteger, sa.ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("input", sa.Text, sa.ForeignKey("input_catalog.name"), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
    )


def downgrade():
    for t in ("input_names", "game_actions", "preferences", "mapping_inputs", "mappings", "modes",
              "profiles", "function_catalog", "output_catalog", "input_catalog"):
        op.drop_table(t)
