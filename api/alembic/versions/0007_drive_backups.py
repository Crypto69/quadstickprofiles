"""Backups of the QuadStick's flash drive.

Two plain new tables, no change to an existing one, so this runs as-is on SQLite
(the desktop build upgrades from its `stamp head` with this chain) and Postgres.
`LargeBinary` is `bytea` on Postgres and `BLOB` on SQLite.

Revision ID: 0007_drive_backups
Revises: 0006_indexes_for_desktop
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_drive_backups"
down_revision = "0006_indexes_for_desktop"
branch_labels = None
depends_on = None

PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade():
    op.create_table(
        "drive_backups",
        sa.Column("id", PK, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "drive_backup_files",
        sa.Column("id", PK, primary_key=True),
        sa.Column("backup_id", PK, sa.ForeignKey("drive_backups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.UniqueConstraint("backup_id", "path", name="uq_drive_backup_files_path"),
    )
    op.create_index("ix_drive_backup_files_backup_id", "drive_backup_files", ["backup_id"])


def downgrade():
    op.drop_index("ix_drive_backup_files_backup_id", table_name="drive_backup_files")
    op.drop_table("drive_backup_files")
    op.drop_table("drive_backups")
