"""Starter profiles.

A template is a profile flagged `is_template`, so "new from template" is the same
copy path as duplicate and there is no second kind of thing to keep in step. The
seed marks the fixtures as templates; they are hidden from the library list by
default so it shows the owner's own profiles, and offered when creating a new one.

Revision ID: 0003_templates
Revises: 0002_firmware_and_mapping_kind
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_templates"
down_revision = "0002_firmware_and_mapping_kind"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("profiles", sa.Column("is_template", sa.Boolean, nullable=False,
                                        server_default=sa.false()))
    op.add_column("profiles", sa.Column("template_note", sa.Text))
    op.create_index("ix_profiles_is_template", "profiles", ["is_template"])


def downgrade():
    op.drop_index("ix_profiles_is_template", table_name="profiles")
    op.drop_column("profiles", "template_note")
    op.drop_column("profiles", "is_template")
