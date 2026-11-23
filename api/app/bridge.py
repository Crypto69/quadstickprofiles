"""DB rows <-> qsprofile.Config. Every parse / validate / convert / write /
render call goes through core/qsprofile; this module only shuttles data."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from qsprofile import Config, Mode as CMode, Mapping as CMapping, validate
from qsprofile import catalog as C
from . import models as M
from .catalog_seed import output_family_group

ROW_OFFSET = 4          # data rows start at spreadsheet row 4 -> row_order 0 == row 4


# A word in a file that the firmware does not know: an output it would skip the row
# for, an input cell it would drop, a function cell it would read as normal. Core
# reports each as a warning, so the file has to be storable to be fixed here, and the
# three keyword columns are foreign keys. Such a word therefore gets a catalog row of
# its own, marked UNKNOWN, on the day a file brings it in. `GET /catalog` serves only
# what core knows (known_input / known_output / known_function), so the editor never
# offers one: it shows it on the row that holds it and nowhere else.
UNKNOWN = "unknown"
_UNKNOWN_SORT = 20_000


def known_input(name: str) -> bool:
    return C.classify_input(name) is not None


def known_output(name: str) -> bool:
    return output_family_group(name) is not None


def known_function(name: str) -> bool:
    return name in C.FUNCTIONS


def _insert_once(db: Session, model, row: dict):
    """Two requests can meet here on the same new name, so the insert is
    `ON CONFLICT DO NOTHING`: the loser simply finds the row already there
    instead of failing the whole request. Postgres and SQLite are the only two
    backends this project supports, and both have it."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"unsupported database backend '{dialect}'")
    db.execute(insert(model).values(**row).on_conflict_do_nothing(index_elements=["name"]))


def ensure_output(db: Session, name: str):
    """Make the output FK hold. Regex-family outputs (kb_*, ir_*) are valid without
    being pre-seeded and are added on first sight under their own group; a word the
    firmware does not know is added as UNKNOWN (see above)."""
    if db.get(M.OutputCatalog, name):
        return
    grp = output_family_group(name)
    _insert_once(db, M.OutputCatalog, dict(
        name=name, grp=grp or UNKNOWN, label=C.output_label(name) or name,
        sort_order=10_000 if grp else _UNKNOWN_SORT))


def ensure_input(db: Session, name: str):
    """Make the input FK hold. Every input core knows is seeded, so anything that
    reaches the insert is a word from a file that the firmware would drop."""
    if db.get(M.InputCatalog, name):
        return
    _insert_once(db, M.InputCatalog, dict(name=name, kind=UNKNOWN, label=name, sort_order=_UNKNOWN_SORT))


def ensure_function(db: Session, name: str):
    """Make the function FK hold. An empty cell is NULL and needs no row; an unknown
    name is kept as read (the device treats the cell as normal) with no parameter
    count, since nothing is known about it."""
    if not name or db.get(M.FunctionCatalog, name):
        return
    _insert_once(db, M.FunctionCatalog, dict(name=name, max_params=None, description=None,
                                             sort_order=_UNKNOWN_SORT))


def check_preference(key: str):
    if key not in C.PREFERENCES:
        raise ValueError(f"Unknown preference '{key}'")


def prune_unknown_words(db: Session, inputs, outputs, functions):
    """Drop the UNKNOWN catalog rows nothing uses any more: the typo was fixed or its
    profile deleted. Run with the catalog seed at start-up, so a word a save may carry
    (profiles._modes_from_body) is only ever one some stored profile still holds.
    Takes the rows the seed has already loaded, so a database with no such word (the
    usual case) costs no query at all."""
    for rows, known, used in (
            (outputs, known_output, lambda names: select(M.Mapping.output).where(M.Mapping.output.in_(names))),
            (functions, known_function, lambda names: select(M.Mapping.function).where(M.Mapping.function.in_(names))),
            (inputs, known_input, lambda names: select(M.MappingInput.input).where(M.MappingInput.input.in_(names))
                .union(select(M.InputName.input).where(M.InputName.input.in_(names))))):
        strangers = [r for r in rows if not known(r.name)]
        if not strangers:
            continue
        in_use = set(db.scalars(used([r.name for r in strangers])))
        for row in strangers:
            if row.name not in in_use:
                db.delete(row)


# ------------------------------------------------------------- Config -> rows
def fill_profile_from_config(db: Session, p: M.Profile, cfg: Config):
    """Replace p's modes and profile-scope preferences with cfg's content."""
    if p.modes:                       # delete first so (profile_id, position) can be reused
        p.modes = []
        db.flush()
    for mode in cfg.modes:
        m = M.Mode(position=mode.number, name=mode.name, label=device_label(mode.name, mode.label),
                   channel=mode.channel or "usb")
        for i, mp in enumerate(mode.mappings):
            if mp.kind == "preference":       # per-mode override: key in A, B as read, value in C
                check_preference(mp.output)
                m.mappings.append(M.Mapping(row_order=i, kind="preference", pref_key=mp.output,
                                            value=mp.value or "", function=None,
                                            column_b=mp.function or None, params=[],
                                            comment=mp.comment or None))
                continue
            ensure_output(db, mp.output)
            ensure_function(db, mp.function)
            for inp in mp.inputs[:8]:
                ensure_input(db, inp)
            # what the parser gave, nothing substituted: an empty function cell stays
            # empty (NULL) so the export is the file that came in
            row = M.Mapping(row_order=i, kind="mapping", output=mp.output,
                            function=mp.function or None,
                            params=list(mp.params or []), comment=mp.comment or None)
            row.inputs = [M.MappingInput(seq=s, input=inp) for s, inp in enumerate(mp.inputs[:8])]
            m.mappings.append(row)
        p.modes.append(m)
    p.preferences = [M.Preference(scope="profile", key=k, value=str(v)) for k, v in cfg.preferences.items()]


def profile_from_config(db: Session, cfg: Config, *, game: str | None = None,
                       firmware: int | None = None) -> M.Profile:
    p = M.Profile(firmware=firmware or C.DEFAULT_FIRMWARE,
                  name=cfg.name, csv_filename=cfg.filename, game=game or cfg.game or None,
                  console=cfg.console,
                  source_url=cfg.source_url or None, format_version=cfg.format_version or "Version 1.4")
    fill_profile_from_config(db, p, cfg)
    return p


# ------------------------------------------------------------- rows -> Config
def device_label(name: str, label: str | None) -> str:
    """What goes in C1 of a mode's `Profile Name` row, on the device and in the
    exported sheet: the mode's name, the one the editor shows (decided 2026-11-19).
    A workbook can carry a different C1 under each tab (a copied tab keeps the old
    cell), and exporting that hidden cell gave the device names the owner never saw.
    The stored `label` is only what the imported file held. Blank is the exception:
    `Profile Name,,,` is legal on the device, the name shown for it ("Mode 2") is a
    stand-in, and the cell stays blank so the file exports as it came in."""
    return name if label else ""


def config_from_profile(p: M.Profile) -> Config:
    cfg = Config(name=p.name, filename=p.csv_filename, game=p.game or "", console=p.console,
                 source_url=p.source_url or "", format_version=p.format_version or "Version 1.4")
    for m in p.modes:
        mode = CMode(number=m.position, name=m.name, label=device_label(m.name, m.label),
                     channel=m.channel)
        for r in m.mappings:
            if r.kind == "preference":
                mode.mappings.append(CMapping(row=r.row_order + ROW_OFFSET, output=r.pref_key,
                                              function=r.column_b or "", params=[], inputs=[],
                                              comment=r.comment or "", kind="preference",
                                              value=r.value or ""))
                continue
            mode.mappings.append(CMapping(row=r.row_order + ROW_OFFSET, output=r.output,
                                          function=r.function or "", params=list(r.params or []),
                                          inputs=[i.input for i in r.inputs], comment=r.comment or ""))
        cfg.modes.append(mode)
    for pref in p.preferences:
        cfg.preferences[pref.key] = pref.value
    return cfg


# ------------------------------------------------------------- actions dict for render()
def actions_for_profile(db: Session, p: M.Profile) -> dict:
    """Shape expected by qsprofile.render: {game, outputs{}, modes{name:{}}, inputs{}}.
    Per-profile game_actions win; otherwise fall back to the shared template for the game."""
    rows = p.game_actions
    if not rows and p.game:
        rows = db.query(M.GameAction).filter(M.GameAction.profile_id.is_(None),
                                             M.GameAction.game == p.game).order_by(M.GameAction.id).all()
    actions = {"game": p.game or "", "outputs": {}, "modes": {}, "inputs": {}}
    for ga in rows:
        if ga.mode_name:
            actions["modes"].setdefault(ga.mode_name, {})[ga.output] = ga.action
        else:
            actions["outputs"][ga.output] = ga.action
    for n in p.input_names:
        actions["inputs"][n.input] = n.name
    return actions


# ------------------------------------------------------------- validation
hidden_drive_modes = C.hidden_drive_modes      # firmware -> emulation modes that hide the drive


def findings_for_profile(p: M.Profile, cfg: Config | None = None) -> list[tuple]:
    """Every rule lives in core; the profile only contributes the firmware it targets,
    which picks the drive-hiding emulation set. The emulation mode itself is read
    from the file's own Preferences block and override rows, never from a column."""
    cfg = cfg or config_from_profile(p)
    return list(validate(cfg, firmware=p.firmware))


def has_errors(findings) -> bool:
    return any(f[0] == "error" for f in findings)
