"""DB rows <-> qsprofile.Config. Every parse / validate / convert / write /
render call goes through core/qsprofile; this module only shuttles data."""
from sqlalchemy.orm import Session
from qsprofile import Config, Mode as CMode, Mapping as CMapping, validate
from qsprofile import catalog as C
from . import models as M
from .catalog_seed import output_family_group

ROW_OFFSET = 4          # data rows start at spreadsheet row 4 -> row_order 0 == row 4


def ensure_output(db: Session, name: str):
    """Regex-family outputs (kb_*, ir_*) are valid without being pre-seeded;
    add them to the catalog on first sight so the FK holds. Unknown -> ValueError.
    Two requests can meet here on the same new name, so the insert is
    `ON CONFLICT DO NOTHING`: the loser simply finds the row already there
    instead of failing the whole request. Postgres and SQLite are the only two
    backends this project supports, and both have it."""
    if db.get(M.OutputCatalog, name):
        return
    grp = output_family_group(name)
    if grp is None:
        raise ValueError(f"Unknown output '{name}'")
    row = dict(name=name, grp=grp, label=C.output_label(name), sort_order=10_000)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"unsupported database backend '{dialect}'")
    db.execute(insert(M.OutputCatalog).values(**row).on_conflict_do_nothing(index_elements=["name"]))


def check_input(name: str):
    if C.classify_input(name) is None:
        raise ValueError(f"Unknown input '{name}'")


def check_function(name: str):
    """Only the name: `mappings.function` is a foreign key to function_catalog, so an
    unknown one cannot be stored. An empty cell is fine (NULL; the device reads it as
    normal). Bad parameters are stored as they are and surface as findings, so the
    file round-trips and the editor can show the row."""
    if name and name not in C.FUNCTIONS:
        raise ValueError(f"Unknown output function '{name}'")


def check_preference(key: str):
    if key not in C.PREFERENCES:
        raise ValueError(f"Unknown preference '{key}'")


# ------------------------------------------------------------- Config -> rows
def fill_profile_from_config(db: Session, p: M.Profile, cfg: Config):
    """Replace p's modes and profile-scope preferences with cfg's content."""
    if p.modes:                       # delete first so (profile_id, position) can be reused
        p.modes = []
        db.flush()
    for mode in cfg.modes:
        m = M.Mode(position=mode.number, name=mode.name, label=mode.label, channel=mode.channel or "usb")
        for i, mp in enumerate(mode.mappings):
            if mp.kind == "preference":       # per-mode override: key in A, B as read, value in C
                check_preference(mp.output)
                m.mappings.append(M.Mapping(row_order=i, kind="preference", pref_key=mp.output,
                                            value=mp.value or "", function=None,
                                            column_b=mp.function or None, params=[],
                                            comment=mp.comment or None))
                continue
            ensure_output(db, mp.output)
            check_function(mp.function)
            for inp in mp.inputs:
                check_input(inp)
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
def config_from_profile(p: M.Profile) -> Config:
    cfg = Config(name=p.name, filename=p.csv_filename, game=p.game or "", console=p.console,
                 source_url=p.source_url or "", format_version=p.format_version or "Version 1.4")
    for m in p.modes:
        mode = CMode(number=m.position, name=m.name, label=m.label, channel=m.channel)
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
