"""Repair the indexes a desktop SQLite file never got.

The desktop build creates its database with `Base.metadata.create_all` and then
`alembic stamp head` (app/standalone.py), so migrations 0001-0003 never run there.
Those three migrations create seven single-column indexes, and until now
`models.py` declared none of them — so every shipped desktop install has the
tables but not the indexes, while its `alembic_version` claims otherwise. The
first migration to touch one of them would fail there with "no such index".

`models.py` now carries `index=True` on the seven columns, which fixes new
desktop databases. This migration fixes the ones already out in the wild:
`CREATE INDEX IF NOT EXISTS` is a no-op on Postgres and on any desktop file
created after the model change, and creates the missing indexes on a desktop
file created before it.

`downgrade()` is deliberately a **no-op**. These indexes belong to migrations
0001-0003; dropping them here would make those migrations' own downgrades fail
on the index they expect to still exist.

Revision ID: 0006_indexes_for_desktop
Revises: 0005_column_b_as_read
Create Date: 2026-09-15
"""
from alembic import op

revision = "0006_indexes_for_desktop"
down_revision = "0005_column_b_as_read"
branch_labels = None
depends_on = None

# (index name, table, column) — must match what 0001-0003 create, and what the
# default naming `index=True` gives the same columns in models.py.
INDEXES = [
    ("ix_modes_profile_id", "modes", "profile_id"),                 # 0001
    ("ix_mappings_mode_id", "mappings", "mode_id"),                 # 0001
    ("ix_preferences_profile_id", "preferences", "profile_id"),     # 0001
    ("ix_game_actions_profile_id", "game_actions", "profile_id"),   # 0001
    ("ix_game_actions_game", "game_actions", "game"),               # 0001
    ("ix_mappings_kind", "mappings", "kind"),                       # 0002
    ("ix_profiles_is_template", "profiles", "is_template"),         # 0003
]


def upgrade():
    # No batch mode: CREATE INDEX IF NOT EXISTS is plain DDL that SQLite and
    # Postgres both accept, and it rewrites no table.
    for name, table, column in INDEXES:
        op.create_index(name, table, [column], if_not_exists=True)


def downgrade():
    """No-op on purpose: the indexes are 0001-0003's to drop, not this one's."""
