"""Profiles CRUD + import / validate / export / convert / card.
All file-format work is delegated to qsprofile (load / validate / convert /
write_csv / write_xlsx / render); this module never touches the formats."""
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from qsprofile import load, convert, write_csv, write_xlsx, render, render_summary
from qsprofile import catalog as C
from qsprofile.catalog import check_csv_filename
from qsprofile.validate import budget as core_budget
from .. import models as M, schemas as S
from ..bridge import (profile_from_config, config_from_profile,
                      actions_for_profile, findings_for_profile, has_errors, ensure_output,
                      ROW_OFFSET)
from ..db import get_session
from ..headers import export_path_header
from ..settings import settings
from ..uploads import read_capped

router = APIRouter(prefix="/profiles", tags=["profiles"])

_LOAD = (selectinload(M.Profile.modes).selectinload(M.Mode.mappings).selectinload(M.Mapping.inputs),
         selectinload(M.Profile.preferences), selectinload(M.Profile.game_actions),
         selectinload(M.Profile.input_names))


def _get(db: Session, profile_id: int) -> M.Profile:
    p = db.scalars(select(M.Profile).options(*_LOAD).where(M.Profile.id == profile_id)).first()
    if not p:
        raise HTTPException(404, f"Profile {profile_id} not found")
    return p


def _iso(dt):
    return dt.isoformat() if dt else None


def _stem(csv_filename: str) -> str:
    """The name that belongs with a `.csv` filename: its stem. The device loads by
    filename and never reads the name, so the names this server invents (a duplicate,
    a conversion) take the stem of the file they will be written as — the pair the
    owner can match up on the stick. `csv_filename_for_name(_stem(f)) == f`."""
    return str(csv_filename or "").rsplit(".", 1)[0]


def _touch(p: M.Profile):
    """`updated_at` only moves on its own when a profiles column changes; a mapping,
    game-action or input-name edit is still an edit, so the library orders by it."""
    p.updated_at = datetime.now(timezone.utc)


def _mapping_out(r: M.Mapping) -> S.MappingOut:
    """A preference row carries its key in `output` on the wire (as in the file), so the
    editor reads one shape; `kind` says which it is."""
    if r.kind == "preference":
        return S.MappingOut(id=r.id, row_order=r.row_order, row=r.row_order + ROW_OFFSET,
                            kind="preference", output=r.pref_key, value=r.value or "",
                            function=r.column_b or "", params=[], inputs=[], comment=r.comment,
                            is_sequence=False)
    inputs = [i.input for i in r.inputs]
    return S.MappingOut(id=r.id, row_order=r.row_order, row=r.row_order + ROW_OFFSET, kind="mapping",
                        output=r.output, value="", function=r.function or "", params=list(r.params or []),
                        inputs=inputs, comment=r.comment, is_sequence=len(inputs) > 1)


def _emulation_mode(p: M.Profile) -> int | None:
    """The profile-scope enable_DS3_emulation row as an int, for the Library's
    drive-hiding warning; None when absent or not a whole number (the validator
    reports that). Nothing else holds the emulation mode (decision D1)."""
    value = next((x.value for x in p.preferences if x.key == "enable_DS3_emulation"), None)
    try:
        return int(str(value).strip()) if value is not None else None
    except ValueError:
        return None


_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


def _finding_order(f):
    """Errors first; within a severity by (mode, row), with file-level findings
    (no mode) after the per-mode ones and a mode-level finding (no row) after that
    mode's rows, so the Problems panel reads top to bottom like the file."""
    mode, row = f[1], f[2]
    return (_SEVERITY_RANK.get(f[0], 3), mode is None, mode or 0, row is None, row or 0)


def _merge_findings(parse_problems, findings):
    """The parser's own problems and the validator's findings, in _finding_order,
    without the same finding said twice (the parser and validate() overlap on a few
    rules). A duplicate is the same severity, mode and row with the same message once
    the whitespace and case are normalised; the sort is stable, so two findings on
    one row keep the order they were found in."""
    seen, merged = set(), []
    for f in list(parse_problems) + list(findings):
        key = (f[0], f[1], f[2], " ".join(str(f[3]).split()).lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(f)
    merged.sort(key=_finding_order)
    return merged


def _out(p: M.Profile) -> S.ProfileOut:
    return S.ProfileOut(
        id=p.id, name=p.name, csv_filename=p.csv_filename, game=p.game, console=p.console,
        firmware=p.firmware, notes=p.notes,
        source_url=p.source_url, is_template=p.is_template, template_note=p.template_note,
        format_version=p.format_version, created_at=_iso(p.created_at), updated_at=_iso(p.updated_at),
        modes=[S.ModeOut(id=m.id, position=m.position, name=m.name, label=m.label, channel=m.channel,
                         mappings=[_mapping_out(r) for r in m.mappings])
               for m in p.modes],
        preferences={x.key: x.value for x in p.preferences},
        game_actions=[S.GameActionOut(id=g.id, output=g.output, action=g.action, mode_name=g.mode_name)
                      for g in p.game_actions],
        input_names={n.input: n.name for n in p.input_names},
    )


def _modes_from_body(db: Session | None, modes: list[S.ModeIn]) -> list[M.Mode]:
    """The mode / mapping / input rows a request body describes. One builder for the
    two callers — the save (PUT, POST) and the live check (POST /profiles/validate) —
    so what the editor is told about a document is what saving it would store.
    `db` is None on the live path: nothing is looked up and nothing is persisted.
    The keyword rules are already applied by the schema (MappingIn), including the
    8-input cap and the preference-key check."""
    out = []
    for pos, mode in enumerate(modes, start=1):
        # C1 may be blank on the device (`Profile Name,,,`): an explicit '' stays '', so
        # GET -> PUT -> export is byte-identical; only an absent label falls back to name.
        m = M.Mode(position=pos, name=mode.name, channel=mode.channel,
                   label=mode.label if mode.label is not None else mode.name)
        m.mappings = []
        for i, mp in enumerate(mode.mappings):
            if mp.kind == "preference":
                m.mappings.append(M.Mapping(row_order=i, kind="preference", pref_key=mp.output,
                                            value=mp.value, function=None, column_b=mp.function or None,
                                            params=[], comment=mp.comment))
                continue
            if db is not None:        # an output the seed does not hold yet (kb_* / ir_*)
                ensure_output(db, mp.output)
            row = M.Mapping(row_order=i, kind="mapping", output=mp.output, function=mp.function or None,
                            params=list(mp.params), comment=mp.comment)
            row.inputs = [M.MappingInput(seq=s, input=inp) for s, inp in enumerate(mp.inputs)]
            m.mappings.append(row)
        out.append(m)
    return out


def _apply_children(db: Session, p: M.Profile, body: S.ProfileCreate):
    if p.modes:                       # delete first so (profile_id, position) can be reused
        p.modes = []
        db.flush()
    p.modes = _modes_from_body(db, body.modes)
    p.preferences = [M.Preference(scope="profile", key=k, value=v) for k, v in body.preferences.items()]
    _apply_game_actions(p, body.game_actions)
    _apply_input_names(p, body.input_names)
    _touch(p)


def _apply_game_actions(p: M.Profile, actions: list[S.GameActionIn]):
    p.game_actions = [M.GameAction(game=p.game or "", output=g.output, action=g.action, mode_name=g.mode_name)
                      for g in actions]


def _apply_input_names(p: M.Profile, names: dict[str, str]):
    p.input_names = [M.InputName(input=k, name=v) for k, v in names.items() if v]


def _copy_labels(src: M.Profile, p: M.Profile):
    """The two label sets a copy must carry across by hand: the game-action names and
    the renamed inputs. Neither is part of the Config, so profile_from_config cannot
    bring them; everything else (modes, rows, comments, preferences) already is."""
    _apply_game_actions(p, [S.GameActionIn(output=g.output, action=g.action, mode_name=g.mode_name)
                            for g in src.game_actions])
    _apply_input_names(p, {n.input: n.name for n in src.input_names})


# ---------------------------------------------------------------- list / create / read
@router.get("", response_model=list[S.ProfileSummary])
def list_profiles(q: str | None = Query(None, description="search by game or name"),
                  validate: bool = Query(False, description="include validation counts (slower)"),
                  templates: bool = Query(False, description="list the starter profiles instead"),
                  db: Session = Depends(get_session)):
    """The library. Templates are a separate shelf, so this shows one or the other."""
    stmt = (select(M.Profile).options(*_LOAD)
            .where(M.Profile.is_template.is_(templates))
            .order_by(M.Profile.updated_at.desc(), M.Profile.id.desc()))
    if q:
        # autoescape, or a search for `_` or `%` would be read as a LIKE wildcard
        # and match every profile instead of the one whose name holds that character
        stmt = stmt.where(M.Profile.game.icontains(q, autoescape=True)
                          | M.Profile.name.icontains(q, autoescape=True))
    out = []
    for p in db.scalars(stmt).all():
        out.append(S.ProfileSummary(
            id=p.id, name=p.name, csv_filename=p.csv_filename, game=p.game, console=p.console,
            emulation_mode=_emulation_mode(p), firmware=p.firmware,
            is_template=p.is_template, template_note=p.template_note,
            mode_count=len(p.modes), updated_at=_iso(p.updated_at),
            validation=S.ValidationOut.from_findings(findings_for_profile(p)) if validate else None))
    return out


@router.post("", response_model=S.ProfileOut, status_code=201)
def create_profile(body: S.ProfileCreate, db: Session = Depends(get_session)):
    p = M.Profile(name=body.name, csv_filename=body.csv_filename, game=body.game, console=body.console,
                  firmware=body.firmware, notes=body.notes, source_url=body.source_url,
                  is_template=body.is_template, template_note=body.template_note)
    _apply_children(db, p, body)
    db.add(p)
    db.commit()
    return _out(_get(db, p.id))


@router.get("/{profile_id}", response_model=S.ProfileOut)
def read_profile(profile_id: int, db: Session = Depends(get_session)):
    return _out(_get(db, profile_id))


@router.put("/{profile_id}", response_model=S.ProfileOut)
def replace_profile(profile_id: int, body: S.ProfileReplace, db: Session = Depends(get_session)):
    p = _get(db, profile_id)
    for k in ("name", "csv_filename", "game", "console", "firmware",
              "notes", "source_url", "is_template", "template_note"):
        setattr(p, k, getattr(body, k))
    _apply_children(db, p, body)
    db.commit()
    return _out(_get(db, profile_id))


@router.patch("/{profile_id}", response_model=S.ProfileOut)
def patch_profile(profile_id: int, body: S.ProfilePatch, db: Session = Depends(get_session)):
    p = _get(db, profile_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "input_names":
            _apply_input_names(p, v or {})
        elif k == "game_actions":
            _apply_game_actions(p, [S.GameActionIn(**g) for g in (v or [])])
        else:
            setattr(p, k, v)
    _touch(p)
    db.commit()
    return _out(_get(db, profile_id))


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: int, db: Session = Depends(get_session)):
    p = _get(db, profile_id)
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- import
@router.post("/import", response_model=S.ImportOut, status_code=201)
async def import_profile(file: UploadFile = File(...), game: str | None = Form(None),
                         name: str | None = Form(None),
                         firmware: int = Form(C.DEFAULT_FIRMWARE),
                         db: Session = Depends(get_session)):
    """Upload a Google-Sheet `.xlsx` download or a device `.csv`; auto-detected by extension."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".xlsx", ".csv"):
        raise HTTPException(415, "Upload a .xlsx (Google Sheet download) or a device .csv")
    data = await read_capped(file)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / (Path(file.filename).name or f"upload{suffix}")
        tmp.write_bytes(data)
        try:
            cfg, problems = load(str(tmp))
        except Exception as e:                       # openpyxl / csv failures
            raise HTTPException(422, f"Could not read {file.filename}: {e}")
    if problem := C.check_firmware(firmware):
        raise HTTPException(422, problem)
    # the name override is typed, not read from the file, so it follows the same line-1
    # rule as the JSON bodies (a line break or non-ASCII is a 422; a comma only warns),
    # and it goes onto the Config before the findings, so they describe what is stored
    if name and (problem := C.unsafe_text(name.replace(",", ""))):
        raise HTTPException(422, f"name: '{name[:30]}' {problem}")
    if name:
        cfg.name = name
    import_findings = _merge_findings(problems, findings_for_profile(M.Profile(firmware=firmware), cfg))

    def refuse(why: str):
        db.rollback()
        raise HTTPException(422, detail={"message": f"Import refused: {why}",
                                         "validation": S.ValidationOut.from_findings(import_findings).model_dump()})
    # errors the database has no way to hold are refused up front, with the findings
    # that explain them; everything else is stored and reported, so the file can be fixed here
    if reasons := _unstorable(cfg):
        refuse("; ".join(reasons))
    try:
        p = profile_from_config(db, cfg, game=game, firmware=firmware)
    except ValueError as e:                      # unknown output / input / function / preference
        refuse(str(e))
    db.add(p)
    try:
        db.commit()
    except IntegrityError as e:                  # a CHECK or FK the pre-checks did not cover
        refuse(f"the database rejected the profile ({e.orig})")
    return S.ImportOut(profile=_out(_get(db, p.id)), findings=S.ValidationOut.from_findings(import_findings))


def _unstorable(cfg) -> list[str]:
    """Why the database could not hold this Config: an Infrared block the data model
    has no shape for, more modes than the position CHECK allows, a mapping whose
    function is not in function_catalog (FK), or a filename the profiles CHECK
    rejects. Each is also a core finding."""
    out = []
    if cfg.infrared_blocks:
        out.append(f"the file contains {cfg.infrared_blocks} Infrared block(s), which this "
                   "tool cannot store; importing it would re-export them as profile modes")
    if len(cfg.modes) > C.MAX_MODES:
        out.append(f"{len(cfg.modes)} modes; the QuadStick allows at most {C.MAX_MODES}")
    if problem := check_csv_filename(cfg.filename):
        out.append(f"A2 must be the profile's filename: {problem}")
    for mode in cfg.modes:
        for m in mode.mappings:
            if m.kind != "preference" and m.function and m.function not in C.FUNCTIONS:
                out.append(f"mode {mode.number} row {m.row}: unknown output function '{m.function}'")
    return out


# ---------------------------------------------------------------- validate
def _validation(p: M.Profile, cfg=None) -> S.ValidationOut:
    """Findings, the firmware budget and the device consequence per severity —
    everything the editor's bottom bar and Problems panel need in one response."""
    cfg = cfg or config_from_profile(p)
    b = core_budget(cfg, p.firmware)
    b["firmware"] = p.firmware or C.DEFAULT_FIRMWARE
    return S.ValidationOut.from_findings(findings_for_profile(p, cfg), budget=b)


@router.get("/{profile_id}/validate", response_model=S.ValidationOut)
def validate_profile(profile_id: int, db: Session = Depends(get_session)):
    return _validation(_get(db, profile_id))


@router.post("/validate", response_model=S.ValidationOut)
def validate_document(body: S.ValidateIn):
    """Validate an unsaved profile document. The editor calls this on every change,
    so live checks never touch the database."""
    p = M.Profile(name=body.name, csv_filename=body.csv_filename, game=body.game, console=body.console,
                  firmware=body.firmware, format_version="Version 1.4")
    p.modes = _modes_from_body(None, body.modes)
    p.preferences = [M.Preference(scope="profile", key=k, value=v) for k, v in body.preferences.items()]
    return _validation(p)


# ---------------------------------------------------------------- export
def _export(db, profile_id, kind, filename):
    p = _get(db, profile_id)
    cfg = config_from_profile(p)
    findings = findings_for_profile(p, cfg)
    if has_errors(findings):
        raise HTTPException(409, detail={"message": "Export refused: fix the validation errors first",
                                         "validation": S.ValidationOut.from_findings(findings).model_dump()})
    fname = filename or p.csv_filename
    _check_export_name(fname)
    out = _export_target(fname if kind == "csv" else Path(fname).with_suffix(".xlsx").name)
    data = write_atomically(out, lambda path: (write_csv if kind == "csv" else write_xlsx)(cfg, path, fname))
    media = "text/csv" if kind == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(data, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{out.name}"',
                             "X-Export-Path": export_path_header(out)})


def write_atomically(out: Path, writer) -> bytes:
    """Call `writer(tmp_path)` on a file of this request's own in the same directory,
    read back those bytes, then move it over `out` in one step. Two exports of the
    same name can no longer interleave, a failed write leaves the previous file in
    place, and the response carries the bytes this request wrote, not a re-read."""
    fd, tmp = tempfile.mkstemp(prefix=f".{out.name}.", suffix=".tmp", dir=out.parent)
    os.close(fd)
    try:
        writer(tmp)
        data = Path(tmp).read_bytes()
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return data


def _check_export_name(fname: str):
    """A path is never a filename: a directory part or an absolute path is a 400
    before the device's own rule (bare name, <= 31 chars, .csv) is applied as a 422."""
    # a backslash counts as a separator too: exports/ is served as an SMB share
    if not fname or Path(fname).name != fname or Path(fname).is_absolute() or "\\" in fname:
        raise HTTPException(400, f"filename must be a bare file name, not a path: '{fname}'")
    if problem := check_csv_filename(fname):
        raise HTTPException(422, f"filename: {problem}")


def _export_target(name: str) -> Path:
    """The file inside `exports/` an export may write. Resolved and checked to sit
    directly in the exports directory. `X-Export-Path` shows the percent-encoded
    form of this path: header values must be Latin-1, and the exports directory can
    sit under a home folder whose name is not."""
    exports = settings.exports_dir.resolve()
    exports.mkdir(parents=True, exist_ok=True)
    out = (exports / name).resolve()
    if out.parent != exports or out.name != name:
        raise HTTPException(400, f"'{name}' does not resolve to a file inside the exports directory")
    return out


@router.get("/{profile_id}/export.csv")
def export_csv(profile_id: int, filename: str | None = Query(None, description="override the .csv filename"),
               db: Session = Depends(get_session)):
    """Device CSV, byte-identical to the QuadStick add-on. Also written to the exports/ share."""
    return _export(db, profile_id, "csv", filename)


@router.get("/{profile_id}/export.xlsx")
def export_xlsx(profile_id: int, filename: str | None = Query(None), db: Session = Depends(get_session)):
    """Workbook in the Google Sheet template layout (for people who still use the add-on)."""
    return _export(db, profile_id, "xlsx", filename)


# ---------------------------------------------------------------- from a template
@router.post("/from-template/{template_id}", response_model=S.ProfileOut, status_code=201)
def create_from_template(template_id: int, body: S.FromTemplateIn, db: Session = Depends(get_session)):
    """Start a profile from a starter one. Same copy path as duplicate, so mappings,
    game-action labels and input names all come across; the copy is never itself a
    template, and it takes its own filename because the device picks files by name."""
    src = _get(db, template_id)
    if not src.is_template:
        raise HTTPException(409, f"Profile {template_id} is not a starter profile")
    cfg = config_from_profile(src)
    cfg.name = body.name
    cfg.filename = body.csv_filename
    p = profile_from_config(db, cfg, game=body.game or src.game, firmware=src.firmware)
    p.notes = f"Started from the '{src.name}' starter profile"
    p.source_url = None
    p.is_template = False
    # the preferences came across with the Config; only the labels need copying
    _copy_labels(src, p)
    db.add(p)
    db.commit()
    return _out(_get(db, p.id))


# ---------------------------------------------------------------- duplicate
@router.post("/{profile_id}/duplicate", response_model=S.ProfileOut, status_code=201)
def duplicate_profile(profile_id: int, name: str | None = Query(None, description="name for the copy"),
                      csv_filename: str | None = Query(None, description="filename for the copy"),
                      db: Session = Depends(get_session)):
    """Copy a profile, including its per-mode preference override rows and comments.
    A copy needs its own `.csv` filename, because the device picks files by filename;
    the default appends `_copy` to the stem, and the default name is that stem, so the
    two agree on the stick (`cvcodww2_copy` / `cvcodww2_copy.csv`). Both stay
    independently settable."""
    src = _get(db, profile_id)
    if csv_filename and (problem := check_csv_filename(csv_filename)):
        raise HTTPException(422, f"csv_filename: {problem}")
    if name and (problem := C.unsafe_text(name.replace(",", ""))):    # line 1: a comma only warns
        raise HTTPException(422, f"name: '{name[:30]}' {problem}")
    fname = csv_filename or C.derived_csv_filename(src.csv_filename, "copy")
    # the derived name is the server's own invention and the user never gets to shorten
    # it, so check it here rather than letting the profiles CHECK turn it into a 500
    if problem := check_csv_filename(fname):
        raise HTTPException(422, f"csv_filename: {problem}")
    cfg = config_from_profile(src)
    # the default name is the filename's own stem, so name and file agree: the device
    # loads by filename and never reads the name, and a pair that disagrees is exactly
    # what makes a stick full of copies unreadable
    cfg.name = name or _stem(fname)
    cfg.filename = fname
    p = profile_from_config(db, cfg, game=src.game, firmware=src.firmware)
    p.notes = src.notes
    p.source_url = src.source_url
    p.is_template, p.template_note = src.is_template, src.template_note
    _copy_labels(src, p)
    db.add(p)
    db.commit()
    return _out(_get(db, p.id))


# ---------------------------------------------------------------- convert
@router.post("/{profile_id}/convert", response_model=S.ConvertOut, status_code=201)
def convert_profile(profile_id: int, body: S.ConvertIn, db: Session = Depends(get_session)):
    """Create a copy under the other console's naming set. Outputs are canonical,
    so this is a rename at export time plus notes for anything that won't carry across.
    The default filename appends `_ps` / `_xbox` and the default name is that stem, so
    the pair agrees on the stick; `name` and `csv_filename` still override either."""
    src = _get(db, profile_id)
    cfg = config_from_profile(src)
    findings = findings_for_profile(src, cfg)
    if has_errors(findings):
        raise HTTPException(409, detail={"message": "Convert refused: fix the validation errors first",
                                         "validation": S.ValidationOut.from_findings(findings).model_dump()})
    new_cfg, notes = convert(cfg, body.target)
    suffix = "ps" if body.target == "playstation" else "xbox"
    suggested = body.csv_filename or C.derived_csv_filename(src.csv_filename, suffix)
    # as in duplicate: a server-derived name must pass the device's rule before insert
    if problem := check_csv_filename(suggested):
        raise HTTPException(422, f"csv_filename: {problem}")
    # as in duplicate, the default name is the suggested filename's stem so the two agree
    new_cfg.name = body.name or _stem(suggested)
    new_cfg.filename = suggested
    p = profile_from_config(db, new_cfg, game=src.game, firmware=src.firmware)
    p.notes = src.notes
    p.source_url = None
    _copy_labels(src, p)
    db.add(p)
    db.commit()
    return S.ConvertOut(profile=_out(_get(db, p.id)), notes=[S.Finding.from_tuple(n) for n in notes],
                        suggested_csv_filename=suggested)


# ---------------------------------------------------------------- card
@router.get("/{profile_id}/card.html", response_class=HTMLResponse)
def card_html(profile_id: int, db: Session = Depends(get_session)):
    """Printable A4 reference card (generated, never stored)."""
    p = _get(db, profile_id)
    cfg = config_from_profile(p)
    return HTMLResponse(render(cfg, actions_for_profile(db, p), findings_for_profile(p, cfg)))


@router.get("/{profile_id}/summary.html", response_class=HTMLResponse)
def summary_html(profile_id: int, db: Session = Depends(get_session)):
    """Compact one-table-per-mode cheat sheet: game action | QuadStick | console button."""
    p = _get(db, profile_id)
    return HTMLResponse(render_summary(config_from_profile(p), actions_for_profile(db, p)))
