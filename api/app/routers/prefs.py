"""Global preferences — the device's own `prefs.csv`.

These sit underneath every profile: `prefs.csv` < a profile's own Preferences <
a per-mode override row (docs/file-format.md). They are stored with
`scope = 'global'` and no profile, so there is exactly one set.
"""
from pathlib import Path
import tempfile
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from qsprofile import catalog as C
from qsprofile import read_prefs_csv, validate_preferences, write_prefs_csv
from .. import models as M, schemas as S
from ..db import get_session
from ..headers import export_path_header
from ..uploads import read_capped
from .profiles import write_atomically, _export_target

router = APIRouter(prefix="/prefs", tags=["preferences"])

PREFS_FILENAME = "prefs.csv"

# which emulation modes hide the drive depends on the firmware, so every endpoint
# takes the firmware the device runs (the settings page passes the one it shows)
Firmware = Query(C.DEFAULT_FIRMWARE, description="firmware the device runs; decides the drive-hiding modes")


def _firmware(fw: int) -> int:
    if problem := C.check_firmware(fw):
        raise HTTPException(422, problem)
    return fw


def _rows(db: Session) -> list[M.Preference]:
    return list(db.scalars(select(M.Preference).where(M.Preference.scope == "global")
                           .order_by(M.Preference.key)).all())


def _as_dict(db: Session) -> dict[str, str]:
    return {r.key: r.value for r in _rows(db)}


# Finding.code values this router keys on. Core findings carry no code, so _coded()
# is the one place that reads a core message; everything after it reads the code.
UNKNOWN_PREFERENCE = "unknown_preference"   # a key the catalog does not know (kept and exported as it is)
NOT_A_PREFS_FILE = "not_a_prefs_file"       # the upload has mode blocks: a profile, not prefs.csv


def _coded(t: tuple, unknown: set[str]) -> S.Finding:
    """A core 4-tuple as a Finding, tagged. read_prefs_csv and validate_preferences
    each note an unknown key (worded differently, both quoting the key); read_prefs_csv
    warns when the file has mode blocks. Recognised here, once, from what core gives."""
    severity, _, _, message = t
    code = None
    if severity == "info" and any(f"'{k}'" in message for k in unknown):
        code = UNKNOWN_PREFERENCE
    elif severity == "warning" and "rather than prefs.csv" in message:
        code = NOT_A_PREFS_FILE
    return S.Finding.from_tuple(t, code=code)


def _unknown(prefs: dict[str, str]) -> set[str]:
    return {k for k in prefs if k not in C.PREFERENCES}


def _findings(prefs: dict[str, str], firmware: int = C.DEFAULT_FIRMWARE) -> list[S.Finding]:
    """Core's rules for the global scope: type, range, choice and threshold checks,
    and the drive-hiding emulation mode as an error, because prefs.csv applies at
    every boot and there is no profile to switch away from. `firmware` is the one
    the caller asked about. An unknown key is reported once, by read_prefs_csv at
    import (the one source), so the UNKNOWN_PREFERENCE finding core's
    validate_preferences makes about it is dropped here."""
    unknown = _unknown(prefs)
    return [f for f in (_coded(t, unknown) for t in validate_preferences(prefs, firmware, "global"))
            if f.code != UNKNOWN_PREFERENCE]


def _has_errors(findings: list[S.Finding]) -> bool:
    return any(f.severity == "error" for f in findings)


@router.get("", response_model=S.PrefsOut)
def read_prefs(firmware: int = Firmware, db: Session = Depends(get_session)):
    """The device-wide settings, with what the QuadStick would make of them."""
    fw = _firmware(firmware)
    prefs = _as_dict(db)
    return S.PrefsOut(preferences=prefs, validation=S.ValidationOut.from_findings(_findings(prefs, fw)))


@router.put("", response_model=S.PrefsOut)
def replace_prefs(body: S.PrefsIn, firmware: int = Firmware, db: Session = Depends(get_session)):
    """Replace the whole set. Values the catalog rejects are refused, not stored."""
    fw = _firmware(firmware)
    findings = _findings(body.preferences, fw)
    if _has_errors(findings):
        raise HTTPException(422, detail={"message": "Some settings are outside what the QuadStick accepts",
                                         "validation": S.ValidationOut.from_findings(findings).model_dump()})
    for row in _rows(db):
        db.delete(row)
    db.flush()
    db.add_all([M.Preference(scope="global", key=k, value=v) for k, v in body.preferences.items()])
    db.commit()
    prefs = _as_dict(db)
    return S.PrefsOut(preferences=prefs, validation=S.ValidationOut.from_findings(_findings(prefs, fw)))


@router.post("/import", response_model=S.PrefsOut)
async def import_prefs(file: UploadFile = File(...), firmware: int = Firmware,
                       db: Session = Depends(get_session)):
    """Upload a `prefs.csv` copied off the QuadStick's flash drive."""
    fw = _firmware(firmware)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Upload the prefs.csv from the QuadStick's flash drive")
    data = await read_capped(file)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / PREFS_FILENAME
        tmp.write_bytes(data)
        try:
            prefs, raw_problems = read_prefs_csv(str(tmp))
        except Exception as e:
            raise HTTPException(422, f"Could not read {file.filename}: {e}")
    problems = [_coded(t, _unknown(prefs)) for t in raw_problems]
    # an empty parse or a profile uploaded by mistake must not wipe the stored set
    mistaken = any(f.code == NOT_A_PREFS_FILE for f in problems)
    if not prefs or mistaken:
        why = ("that file is a profile, not the device's prefs.csv" if mistaken
               else f"no settings were found in {file.filename}")
        raise HTTPException(422, detail={
            "message": f"Import refused: {why}; the stored settings are unchanged",
            "validation": S.ValidationOut.from_findings(problems).model_dump()})
    for row in _rows(db):
        db.delete(row)
    db.flush()
    db.add_all([M.Preference(scope="global", key=k, value=v) for k, v in prefs.items()])
    db.commit()
    stored = _as_dict(db)
    # the parser's problems (the one UNKNOWN_PREFERENCE source) and then the value rules
    findings = problems + [f for f in _findings(stored, fw) if f not in problems]
    return S.PrefsOut(preferences=stored, validation=S.ValidationOut.from_findings(findings))


@router.get("/export.csv")
def export_prefs(firmware: int = Firmware, db: Session = Depends(get_session)):
    """The `prefs.csv` to copy back onto the flash drive."""
    fw = _firmware(firmware)
    prefs = _as_dict(db)
    if not prefs:
        raise HTTPException(409, "There are no device settings to export yet")
    findings = _findings(prefs, fw)
    if _has_errors(findings):
        raise HTTPException(409, detail={"message": "Export refused: fix the settings first",
                                         "validation": S.ValidationOut.from_findings(findings).model_dump()})
    out = _export_target(PREFS_FILENAME)
    data = write_atomically(out, lambda path: write_prefs_csv(prefs, path))
    return Response(data, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{PREFS_FILENAME}"',
                             "X-Export-Path": export_path_header(out)})
