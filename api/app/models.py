"""SQLAlchemy 2 models. Mirrors docs/data-model.md, plus:
  - input_catalog.jack / sort_order   (DIGITAL_JACKS from catalog.py)
  - input_names                        per-profile display names for inputs ("lip" -> "Chin switch")
  - profiles.format_version            the CSV header token, kept so exports stay byte-identical
Outputs are stored canonically (PlayStation names); `console` is applied on export/display.
There is no emulation-mode or channel column (decision D1, migration 0004): the device
reads the emulation mode from the `enable_DS3_emulation` preference row and the
channel from each mode's C3, so those are the only places the app keeps them.
Postgres-only CHECK constraints (regex) live in the Alembic migration; the API
layer enforces the same rules with Pydantic so SQLite test runs behave the same."""
from datetime import datetime
from sqlalchemy import (BigInteger, Boolean, Integer, SmallInteger, Text, ForeignKey, JSON, DateTime,
                        UniqueConstraint, CheckConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from qsprofile import catalog as C
from .db import Base

PK = BigInteger().with_variant(Integer, "sqlite")
JSONType = JSON().with_variant(JSONB(), "postgresql")


class InputCatalog(Base):
    __tablename__ = "input_catalog"
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str | None] = mapped_column(Text)          # mouthpiece / side / lip / joystick / digital / usb / legacy
    tube: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)        # sip / puff
    strength: Mapped[str | None] = mapped_column(Text)      # hard / soft
    label: Mapped[str | None] = mapped_column(Text)
    jack: Mapped[str | None] = mapped_column(Text)          # digital_in_* -> physical jack
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class OutputCatalog(Base):
    __tablename__ = "output_catalog"
    name: Mapped[str] = mapped_column(Text, primary_key=True)   # canonical (PlayStation) name
    grp: Mapped[str | None] = mapped_column(Text)               # button / dpad / stick / system / other / keyboard / ir
    ps_glyph: Mapped[str | None] = mapped_column(Text)
    xbox_name: Mapped[str | None] = mapped_column(Text)
    xbox_glyph: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FunctionCatalog(Base):
    __tablename__ = "function_catalog"
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    max_params: Mapped[int | None] = mapped_column(SmallInteger)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("console in ('playstation','xbox')", name="ck_profiles_console"),
        CheckConstraint(f"firmware in ({','.join(str(f) for f in C.FIRMWARE_VERSIONS)})",
                        name="ck_profiles_firmware"),
    )
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    csv_filename: Mapped[str] = mapped_column(Text, nullable=False)
    game: Mapped[str | None] = mapped_column(Text)
    console: Mapped[str] = mapped_column(Text, nullable=False, default="playstation", server_default="playstation")
    notes: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    format_version: Mapped[str] = mapped_column(Text, nullable=False, default="Version 1.4",
                                                server_default="Version 1.4")
    # which firmware this profile targets; decides the drive-hiding emulation modes
    firmware: Mapped[int] = mapped_column(Integer, nullable=False, default=C.DEFAULT_FIRMWARE,
                                          server_default=str(C.DEFAULT_FIRMWARE))
    # a starter profile to copy from, rather than one of the owner's own
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                              server_default=text("false"))
    template_note: Mapped[str | None] = mapped_column(Text)     # what this starter is for
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())

    modes: Mapped[list["Mode"]] = relationship(back_populates="profile", cascade="all, delete-orphan",
                                               order_by="Mode.position")
    preferences: Mapped[list["Preference"]] = relationship(
        cascade="all, delete-orphan", order_by="Preference.id",
        primaryjoin="and_(Profile.id==Preference.profile_id, Preference.scope=='profile')")
    game_actions: Mapped[list["GameAction"]] = relationship(cascade="all, delete-orphan",
                                                            order_by="GameAction.id")
    input_names: Mapped[list["InputName"]] = relationship(cascade="all, delete-orphan",
                                                          order_by="InputName.input")


class Mode(Base):
    __tablename__ = "modes"
    __table_args__ = (
        UniqueConstraint("profile_id", "position", name="uq_modes_profile_position"),
        CheckConstraint("position between 1 and 16", name="ck_modes_position"),
    )
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)     # = mode number
    name: Mapped[str] = mapped_column(Text, nullable=False)                 # sheet tab name
    label: Mapped[str] = mapped_column(Text, nullable=False)                # C1
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="usb", server_default="usb")

    profile: Mapped[Profile] = relationship(back_populates="modes")
    mappings: Mapped[list["Mapping"]] = relationship(back_populates="mode", cascade="all, delete-orphan",
                                                     order_by="Mapping.row_order")


class Mapping(Base):
    """One row of a mode sheet. `kind` tells the two shapes apart:
      "mapping"    — an ordinary output/function/inputs row; `output` is set. An
                     empty function cell is NULL (the device treats it as normal;
                     the bytes must round-trip, so it is never turned into a word).
      "preference" — a per-mode preference override (A = key, C = value); `pref_key`
                     and `value` are set, `output` and `function` are NULL. The device
                     ignores column B on such a row; it is kept verbatim in `column_b`
                     so the file round-trips. See docs/file-format.md; unverified on a
                     device, so read-only in the UI."""
    __tablename__ = "mappings"
    __table_args__ = (
        UniqueConstraint("mode_id", "row_order", name="uq_mappings_mode_row"),
        CheckConstraint("kind in ('mapping','preference')", name="ck_mappings_kind"),
        CheckConstraint("(kind = 'mapping'    and output is not null and pref_key is null and column_b is null) or "
                        "(kind = 'preference' and output is     null and pref_key is not null and function is null)",
                        name="ck_mappings_shape"),
    )
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    mode_id: Mapped[int] = mapped_column(ForeignKey("modes.id", ondelete="CASCADE"), nullable=False)
    row_order: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="mapping", server_default="mapping")
    output: Mapped[str | None] = mapped_column(ForeignKey("output_catalog.name"))
    pref_key: Mapped[str | None] = mapped_column(Text)                      # kind == "preference"
    value: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    function: Mapped[str | None] = mapped_column(ForeignKey("function_catalog.name"))   # NULL = empty cell
    column_b: Mapped[str | None] = mapped_column(Text)                      # kind == "preference": B as read
    params: Mapped[list] = mapped_column(JSONType, nullable=False, default=list, server_default=text("'[]'"))
    comment: Mapped[str | None] = mapped_column(Text)                       # never exported

    mode: Mapped[Mode] = relationship(back_populates="mappings")
    inputs: Mapped[list["MappingInput"]] = relationship(cascade="all, delete-orphan",
                                                        order_by="MappingInput.seq")


class MappingInput(Base):
    __tablename__ = "mapping_inputs"
    __table_args__ = (CheckConstraint("seq between 0 and 7", name="ck_mapping_inputs_seq"),)
    mapping_id: Mapped[int] = mapped_column(ForeignKey("mappings.id", ondelete="CASCADE"), primary_key=True)
    seq: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    input: Mapped[str] = mapped_column(ForeignKey("input_catalog.name"), nullable=False)


class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (CheckConstraint("scope in ('global','profile','mode')", name="ck_preferences_scope"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    mode_id: Mapped[int | None] = mapped_column(ForeignKey("modes.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class GameAction(Base):
    __tablename__ = "game_actions"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))  # null = shared template
    game: Mapped[str] = mapped_column(Text, nullable=False)
    mode_name: Mapped[str | None] = mapped_column(Text)                     # null = every mode
    output: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)


class InputName(Base):
    """Per-profile display name for an input, e.g. lip -> "Chin switch"."""
    __tablename__ = "input_names"
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    input: Mapped[str] = mapped_column(ForeignKey("input_catalog.name"), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
