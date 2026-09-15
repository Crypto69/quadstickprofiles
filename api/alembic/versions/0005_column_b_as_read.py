"""Keep column B of a mode row exactly as the file has it.

Two rows the table could not hold as the device reads them:

- A mapping row with an **empty** function cell (`x,,lip,`). The device treats it
  as `normal`, but the bytes must round-trip, so core now keeps `Mapping.function
  == ""`. `mappings.function` is a foreign key to `function_catalog`, so it becomes
  nullable: NULL is the empty cell. It loses its `normal` server default so that
  nothing can quietly turn an empty cell into a word.
- A per-mode override row with a **filled** column B (`mouse_speed,normal,120,`).
  The firmware ignores column B on a preference row and reads the value from C,
  but the text must come back out unchanged. It is free text, not a function name,
  so it gets its own column, `column_b`; `function` is NULL on such a row.

`ck_mappings_shape` grows the two rules. Existing override rows carried a dummy
`normal` in `function` (nothing else satisfied the FK); the upgrade sets it to
NULL, which is what they exported before. The downgrade puts `normal` back into
every NULL `function` (the device reads an empty cell that way) and drops
`column_b`, so an override row's column B is the one thing it cannot keep.

Revision ID: 0005_column_b_as_read
Revises: 0004_emulation_mode_in_the_file
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_column_b_as_read"
down_revision = "0004_emulation_mode_in_the_file"
branch_labels = None
depends_on = None

OLD_SHAPE = ("(kind = 'mapping'    and output is not null and pref_key is null) or "
             "(kind = 'preference' and output is     null and pref_key is not null)")
NEW_SHAPE = ("(kind = 'mapping'    and output is not null and pref_key is null and column_b is null) or "
             "(kind = 'preference' and output is     null and pref_key is not null and function is null)")


def upgrade():
    op.add_column("mappings", sa.Column("column_b", sa.Text))
    op.alter_column("mappings", "function", existing_type=sa.Text, nullable=True, server_default=None)
    op.execute("update mappings set function = null where kind = 'preference'")
    op.drop_constraint("ck_mappings_shape", "mappings", type_="check")
    op.create_check_constraint("ck_mappings_shape", "mappings", NEW_SHAPE)


def downgrade():
    op.drop_constraint("ck_mappings_shape", "mappings", type_="check")
    op.create_check_constraint("ck_mappings_shape", "mappings", OLD_SHAPE)
    op.execute("update mappings set function = 'normal' where function is null")
    op.alter_column("mappings", "function", existing_type=sa.Text, nullable=False, server_default="normal")
    op.drop_column("mappings", "column_b")
