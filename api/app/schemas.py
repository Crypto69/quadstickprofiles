"""Pydantic request/response shapes. Keyword fields are validated against the
catalogs here so the API can never store a name the device would reject."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from qsprofile import catalog as C
from qsprofile.catalog import check_csv_filename, unsafe_text
from .catalog_seed import output_family_group

Console = Literal["playstation", "xbox"]
Severity = Literal["error", "warning", "info"]
# a mode's C3 cell: which link its outputs go out on. `both` and `none` are what the
# firmware accepts too; the validator warns when an output cannot reach its link.
Channel = Literal["none", "usb", "bluetooth", "both"]


def _safe(v):
    """Decision D4: nothing that reaches write_csv may carry a comma, a line break or
    non-ASCII. write_csv never quotes and the firmware never unquotes, so a comma
    shifts the cells, a line break forges a new line and non-ASCII would become '?'.
    core's validate() reports the same cells as errors; the save path refuses them."""
    if v is not None and (problem := unsafe_text(v)):
        raise ValueError(f"'{v[:30]}' {problem}")
    return v


def _line1(v):
    """Line 1 of the file (title, sheet URL) is special: the firmware only reads its
    first word, so a comma cannot shift a block — core warns that the name reads back
    cut short. A line break or non-ASCII is still refused."""
    if v is not None and (problem := unsafe_text(v.replace(",", ""))):
        raise ValueError(f"'{v[:30]}' {problem}")
    return v


def _check_filename(v: str) -> str:
    """The device's filename rule (bare name, <= 31 chars, .csv). A path is never a
    filename, so `../x.csv` fails here before it can reach the exports directory."""
    problem = check_csv_filename(v)
    if problem:
        raise ValueError(f"csv_filename: {problem}")
    return v


# ---------------------------------------------------------------- catalog
class InputEntry(BaseModel):
    name: str
    kind: str | None
    tube: str | None
    action: str | None
    strength: str | None
    label: str | None
    jack: str | None


class OutputEntry(BaseModel):
    name: str
    grp: str | None
    ps_glyph: str | None
    xbox_name: str | None
    xbox_glyph: str | None
    label: str | None


class FunctionEntry(BaseModel):
    name: str
    max_params: int | None
    description: str | None


class CatalogOut(BaseModel):
    inputs: list[InputEntry]
    outputs: list[OutputEntry]
    functions: list[FunctionEntry]
    tubes: dict[str, str]
    tube_order: list[str]
    joystick_directions: list[str]
    joystick_zones: list[str]
    digital_jacks: dict[int, str]
    xbox_to_ps: dict[str, str]
    no_xbox_equivalent: list[str]
    mode_change_outputs: list[str]
    output_families: dict[str, str]        # regex fallbacks for kb_* / ir_*
    # firmware knowledge the editor needs (Stage 0)
    preferences: dict[str, dict]           # 61 keys: label, category, editor, default, range, docs
    preference_categories: list[str]
    mode_overridable: list[str]            # keys a per-mode override row may set
    emulation_modes: dict[int, str]
    hidden_drive_modes: dict[int, list[int]]   # firmware -> emulation modes that hide the drive
    firmware_versions: list[int]
    default_firmware: int
    legacy_inputs: dict[str, str]          # accepted but warned-about older input names
    limits: dict[str, int]                 # max modes / rows per mode / keyword chars / line bytes / function param


# ---------------------------------------------------------------- findings
class Finding(BaseModel):
    severity: Severity
    mode: int | None
    row: int | None
    message: str
    # core findings are 4-tuples with no code; a router that must recognise one kind of
    # finding again later (prefs: the unknown-key note) tags it here and keys on this,
    # never on the message text
    code: str | None = None

    @classmethod
    def from_tuple(cls, t, code: str | None = None):
        return cls(severity=t[0], mode=t[1], row=t[2], message=t[3], code=code)


# What the device actually does, per severity. The editor shows this verbatim in its
# bottom bar, so the user reads a consequence rather than a count.
CONSEQUENCE = {
    "error": "The QuadStick will not read this profile correctly. Export is blocked until these are fixed.",
    "warning": "The QuadStick still loads this profile, but these rows will not behave as you expect.",
    # Info is not a lesser problem, it is not a problem: it describes what the
    # profile does. A deliberate design — a chin press that fires an action and
    # changes mode in one go — lands here, and the wording must not imply it is
    # something the owner left half-finished.
    "info": "Nothing to fix. These notes describe what this profile does.",
}


class ModeBudget(BaseModel):
    number: int
    name: str
    rows_used: int
    rows_free: int
    rows_active: int              # rows that actually have an input
    unused_inputs: list[str]      # mouthpiece / side / lip / jack inputs still free here


class Budget(BaseModel):
    """Firmware capacity used, for the editor's "Unused rows: N of 128" counters."""
    modes_used: int
    modes_max: int
    rows_max: int
    modes: list[ModeBudget]
    preference_rows: int
    preference_rows_max: int
    firmware: int


class ValidationOut(BaseModel):
    errors: int
    warnings: int
    info: int
    findings: list[Finding]
    consequence: dict[str, str] = Field(default_factory=dict)   # only the severities present
    budget: Budget | None = None
    unused_inputs: list[str] = Field(default_factory=list)      # free in every mode

    @classmethod
    def from_findings(cls, findings, budget: dict | None = None):
        """`findings`: core tuples, or Findings a router has already tagged."""
        fs = [f if isinstance(f, Finding) else Finding.from_tuple(f) for f in findings]
        present = {f.severity for f in fs}
        modes = (budget or {}).get("modes", [])
        free_everywhere = sorted(set.intersection(*[set(m["unused_inputs"]) for m in modes])) if modes else []
        return cls(errors=sum(f.severity == "error" for f in fs),
                   warnings=sum(f.severity == "warning" for f in fs),
                   info=sum(f.severity == "info" for f in fs), findings=fs,
                   consequence={k: v for k, v in CONSEQUENCE.items() if k in present},
                   budget=Budget(**budget) if budget else None,
                   unused_inputs=free_everywhere)


# ---------------------------------------------------------------- profile bodies
class MappingIn(BaseModel):
    """Either an ordinary mapping (`output` set) or a per-mode preference override
    (`kind="preference"`, `output` is the preference key, `value` its value)."""
    kind: Literal["mapping", "preference"] = "mapping"
    output: str                              # an output name, or a preference key when kind="preference"
    value: str = ""                          # preference override value
    # column B. On a mapping row: a function name; None (not given) means normal, ""
    # is an empty cell, which the device also reads as normal but which must round-trip
    # as empty. On a preference row: free text the device ignores, kept as read.
    # validate_default so that a row posted without one still goes through _function.
    function: str | None = Field(default=None, validate_default=True)
    # as stored (see MappingOut): an import keeps `repeat five 2000` and `repeat 1 2 3`
    # verbatim, and what GET returns must PUT back, so the count and the whole-number
    # rules are core findings the editor shows against the row (export is blocked by
    # has_errors), not a 422 it can only show as "request failed".
    params: list[int | float | str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list, max_length=8)
    comment: str | None = None                # never exported, so free text

    _text = field_validator("value")(_safe)   # the override value is a cell in the file

    @field_validator("function")
    @classmethod
    def _function(cls, v, info):
        if info.data.get("kind", "mapping") == "preference":
            return cls._column_b(v)
        if v is None:
            return "normal"
        if v and v not in C.FUNCTIONS:
            raise ValueError(f"Unknown output function '{v}'")
        return v

    @classmethod
    def _column_b(cls, v):
        """An override row's column B: text the device ignores, but a cell in the file."""
        return _safe(v) if v else ""

    @field_validator("inputs")
    @classmethod
    def _inputs(cls, v):
        for i in v:
            if C.classify_input(i) is None:
                raise ValueError(f"Unknown input '{i}'")
        return v

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "preference":
            if self.output not in C.PREFERENCES:
                raise ValueError(f"Unknown preference '{self.output}'")
            if self.inputs:
                raise ValueError("A preference override row takes no inputs")
            if self.params:
                raise ValueError("A preference override row takes no function parameters")
            return self
        if output_family_group(self.output) is None:
            raise ValueError(f"Unknown output '{self.output}' (outputs are stored under PlayStation names)")
        if self.value:
            raise ValueError("`value` is only for kind='preference' rows")
        # an empty function cell with parameters would export as `x, 5,lip,`, which the
        # device reads as the function '5'. No import can store that (the parser reads
        # the cell as the function) and core has no rule for it, so it stays a 422.
        if self.params and not self.function:
            raise ValueError(f"an empty function cell takes no parameters, got {len(self.params)}")
        return self


class MappingOut(BaseModel):
    """What is stored, as stored. Deliberately not a MappingIn: the input rules
    (catalog names, the text rule) must never make a row that core accepted and the
    database holds unreadable. Bad values are findings."""
    id: int
    row_order: int
    row: int                     # spreadsheet row (row_order + 4), for cross-referencing findings
    kind: Literal["mapping", "preference"] = "mapping"
    output: str
    value: str = ""
    function: str = ""           # column B as stored: "" is an empty cell (or an override row's empty B)
    params: list[int | float | str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    comment: str | None = None
    is_sequence: bool = False    # 2+ inputs: performed in order, C first


class ModeIn(BaseModel):
    # no 31-character cap (see ModeOut): a device CSV's C1 label becomes the mode name,
    # and what an import stored must PUT back. Core has no length rule for C1 either.
    name: str = Field(min_length=1)
    label: str | None = None                  # C1. Absent: the name stands in. "": the C1 cell is
                                              # blank on the device, and stays blank (see profiles.py)
    channel: Channel = "usb"
    mappings: list[MappingIn] = Field(default_factory=list)

    _text = field_validator("name", "label")(_safe)


class ModeOut(BaseModel):
    """Permissive on purpose (see MappingOut): a device CSV's C1 label becomes the
    mode name and has no 31-character limit, and C3 may hold any word."""
    id: int
    position: int
    name: str
    label: str = ""
    channel: str = "usb"
    mappings: list[MappingOut] = Field(default_factory=list)


class GameActionIn(BaseModel):
    """A game's name for what an output does ("right_2" -> "Fire"), for the card."""
    output: str
    action: str                               # card only, never in the file: free text
    mode_name: str | None = None              # must name a mode, so it follows the mode rule

    _text = field_validator("mode_name")(_safe)

    @field_validator("output")
    @classmethod
    def _output(cls, v):
        if output_family_group(v) is None:
            raise ValueError(f"Unknown output '{v}' (outputs are stored under PlayStation names)")
        return v


class ProfileMeta(BaseModel):
    """Fields every profile write may set. `name` may be blank: a device CSV with an
    empty title imports (the firmware never reads line 1's title) and what GET
    returns must PUT back. A new identity typed by the user (ProfilePatch,
    FromTemplateIn) still needs a name."""
    name: str
    csv_filename: str
    game: str | None = None
    console: Console = "playstation"
    # no emulation_mode or channel here (decision D1): the file's enable_DS3_emulation
    # preference row and each mode's `channel` are the only places the device reads them
    # the firmware the profile targets; decides which emulation modes hide the drive
    firmware: int = C.DEFAULT_FIRMWARE
    notes: str | None = None
    source_url: str | None = None
    # a starter profile to copy from, rather than one of the owner's own
    is_template: bool = False
    template_note: str | None = None

    _fn = field_validator("csv_filename")(_check_filename)
    _line1 = field_validator("name", "source_url")(_line1)

    @field_validator("firmware")
    @classmethod
    def _firmware(cls, v):
        if v not in C.FIRMWARE_VERSIONS:
            raise ValueError(f"Unknown firmware {v}; known: {', '.join(map(str, C.FIRMWARE_VERSIONS))}")
        return v


class ProfileCreate(ProfileMeta):
    modes: list[ModeIn] = Field(default_factory=list, max_length=16)
    preferences: dict[str, str] = Field(default_factory=dict)
    game_actions: list[GameActionIn] = Field(default_factory=list)
    input_names: dict[str, str] = Field(default_factory=dict)

    @field_validator("input_names")
    @classmethod
    def _input_names(cls, v):
        for i in v:
            if C.classify_input(i) is None:
                raise ValueError(f"Unknown input '{i}'")
        return v

    @field_validator("preferences")
    @classmethod
    def _preferences(cls, v):
        for k, val in v.items():                # each is a cell of the Preferences block
            _safe(k)
            _safe(val)
        return v


class ProfileReplace(ProfileCreate):
    """PUT body: the whole document; children are replaced."""


class ProfilePatch(BaseModel):
    """PATCH body: metadata only, all optional."""
    name: str | None = Field(default=None, min_length=1)
    csv_filename: str | None = None
    game: str | None = None
    console: Console | None = None
    firmware: int | None = None
    notes: str | None = None
    source_url: str | None = None
    is_template: bool | None = None
    template_note: str | None = None
    input_names: dict[str, str] | None = None
    game_actions: list[GameActionIn] | None = None

    _line1 = field_validator("name", "source_url")(_line1)

    @field_validator("firmware")
    @classmethod
    def _firmware(cls, v):
        if v is not None and v not in C.FIRMWARE_VERSIONS:
            raise ValueError(f"Unknown firmware {v}; known: {', '.join(map(str, C.FIRMWARE_VERSIONS))}")
        return v

    @field_validator("csv_filename")
    @classmethod
    def _fn(cls, v):
        return None if v is None else _check_filename(v)

    @field_validator("input_names")
    @classmethod
    def _input_names(cls, v):
        for i in v or {}:
            if C.classify_input(i) is None:
                raise ValueError(f"Unknown input '{i}'")
        return v


class GameActionOut(BaseModel):
    id: int
    output: str
    action: str
    mode_name: str | None = None


class ProfileSummary(BaseModel):
    id: int
    name: str
    csv_filename: str
    game: str | None
    console: Console
    # derived: the profile-scope enable_DS3_emulation row as an int, else None. It is
    # not stored anywhere else; the Library uses it for its drive-hiding warning.
    emulation_mode: int | None
    firmware: int
    is_template: bool
    template_note: str | None
    mode_count: int
    updated_at: str | None
    validation: ValidationOut | None = None   # counts + findings; omitted when not requested


class ProfileOut(BaseModel):
    """The stored document. Not a ProfileMeta: a blank title or a bad A2 in an
    imported file is a rule-1 finding on a profile that must still read back."""
    id: int
    name: str
    csv_filename: str
    game: str | None = None
    console: Console = "playstation"
    firmware: int = C.DEFAULT_FIRMWARE
    notes: str | None = None
    source_url: str | None = None
    is_template: bool = False
    template_note: str | None = None
    format_version: str
    created_at: str | None
    updated_at: str | None
    modes: list[ModeOut]
    preferences: dict[str, str]
    game_actions: list[GameActionOut]
    input_names: dict[str, str]


class ImportOut(BaseModel):
    profile: ProfileOut
    findings: ValidationOut         # includes import-time problems (e.g. stale Reference Card sheet)


class ConvertIn(BaseModel):
    target: Console
    name: str | None = None
    csv_filename: str | None = None

    _line1 = field_validator("name")(_line1)

    @field_validator("csv_filename")
    @classmethod
    def _fn(cls, v):
        return None if v is None else _check_filename(v)


class ConvertOut(BaseModel):
    profile: ProfileOut
    notes: list[Finding]
    suggested_csv_filename: str


# ---------------------------------------------------------------- stateless validate
class ValidateIn(BaseModel):
    """Body for POST /profiles/validate: a profile document that has not been saved.
    The editor posts the in-progress document on every change and gets findings plus
    the budget back, so live checks never write to the database.

    Permissive on purpose (like the Out models): a blank name, a bad csv_filename, a
    17th mode or a comma in a cell come back as the findings the editor can show
    against the field, not as a 422 the editor can only show as "request failed".
    Mode rows keep the keyword rules, because the editor can only produce catalog
    keywords; the free-text cells (mode name and label, override values, preference
    values) are left to core's validate(), which reports them as errors."""
    name: str = ""
    csv_filename: str = ""
    game: str | None = None
    console: Console = "playstation"
    firmware: int = C.DEFAULT_FIRMWARE
    notes: str | None = None
    source_url: str | None = None
    is_template: bool = False
    template_note: str | None = None
    modes: list["ModeDraft"] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)

    @field_validator("firmware")
    @classmethod
    def _firmware(cls, v):
        if v not in C.FIRMWARE_VERSIONS:
            raise ValueError(f"Unknown firmware {v}; known: {', '.join(map(str, C.FIRMWARE_VERSIONS))}")
        return v


class MappingDraft(MappingIn):
    """A MappingIn whose free-text cells are left to core's findings (live checks)."""
    @field_validator("value")
    @classmethod
    def _text(cls, v):
        return v

    @classmethod
    def _column_b(cls, v):
        return v or ""


class ModeDraft(ModeIn):
    """A ModeIn whose name and label are left to core's findings (live checks); a
    name the user has just cleared is a document to check, not a bad request."""
    name: str = ""
    mappings: list[MappingDraft] = Field(default_factory=list)

    @field_validator("name", "label")
    @classmethod
    def _text(cls, v):
        return v


# ---------------------------------------------------------------- global preferences
class PrefsIn(BaseModel):
    """The device-wide settings (prefs.csv). Keys are checked against the catalog in
    the router, where the range and choice rules live with their messages."""
    preferences: dict[str, str] = Field(default_factory=dict)


class PrefsOut(BaseModel):
    preferences: dict[str, str]
    validation: ValidationOut


class FromTemplateIn(BaseModel):
    """Body for POST /profiles/from-template/{id}: the new profile's own identity."""
    name: str = Field(min_length=1)
    csv_filename: str
    game: str | None = None

    _fn = field_validator("csv_filename")(_check_filename)
    _line1 = field_validator("name")(_line1)
