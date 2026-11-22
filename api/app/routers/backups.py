"""Backups of the QuadStick's flash drive.

The API cannot see the drive: on the NAS it is plugged into another computer, and
the browser is what can read it. So the web app reads every file off the drive (a
folder picker, or the desktop shell's own folder dialog) and posts them here, and
a restore hands the same bytes back as one .zip to copy onto the drive by hand —
the copy onto the device stays manual, as every export does.

Files are stored exactly as read and never parsed: a backup has to keep a file this
app cannot read (joystick.bin, a profile with errors) as faithfully as one it can.
"""
import re
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as M, schemas as S
from ..db import get_session
from ..headers import export_path_header
from ..settings import settings
from ..uploads import read_capped
from .profiles import _export_target, write_atomically

router = APIRouter(prefix="/backups", tags=["backups"])

MAX_FILES = 500
# What a computer leaves on a removable drive. Never the owner's files, and the
# firmware deletes dot-files at boot anyway, so restoring them would be pointless.
SYSTEM_FOLDERS = {"system volume information", "$recycle.bin"}
ZIP_NAME = re.compile(r"[A-Za-z0-9._-]{1,80}\.zip")


def clean_path(raw: str) -> str | None:
    """The drive-relative path to store, `None` for a system file to leave out, or
    a 400 for anything that could point outside the drive when it is unzipped."""
    path = raw.replace("\\", "/")
    parts = path.split("/")
    if not path or path.startswith("/") or ":" in path or any(p in ("", ".", "..") for p in parts):
        raise HTTPException(400, f"'{raw}' is not a path inside the drive")
    if any(p.startswith(".") or p.lower() in SYSTEM_FOLDERS for p in parts):
        return None
    return path


def _utc(dt: datetime) -> datetime:
    # SQLite hands a timezone-aware column back naive; every value here was UTC
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _out(b: M.DriveBackup, files: list[tuple[str, int]]) -> S.BackupOut:
    return S.BackupOut(id=b.id, created_at=_utc(b.created_at).isoformat(),
                       file_count=len(files), total_bytes=sum(size for _, size in files),
                       files=[S.BackupFileOut(path=p, size=size) for p, size in files])


def _get(db: Session, backup_id: int) -> M.DriveBackup:
    b = db.get(M.DriveBackup, backup_id)
    if b is None:
        raise HTTPException(404, f"There is no backup {backup_id}")
    return b


@router.get("", response_model=list[S.BackupOut])
def list_backups(db: Session = Depends(get_session)):
    """Newest first. Names and sizes only; the bytes stay in the database."""
    backups = db.scalars(select(M.DriveBackup).order_by(M.DriveBackup.created_at.desc(),
                                                        M.DriveBackup.id.desc())).all()
    files: dict[int, list[tuple[str, int]]] = {b.id: [] for b in backups}
    rows = db.execute(select(M.DriveBackupFile.backup_id, M.DriveBackupFile.path, M.DriveBackupFile.size)
                      .order_by(M.DriveBackupFile.path))
    for backup_id, path, size in rows:
        files[backup_id].append((path, size))
    return [_out(b, files[b.id]) for b in backups]


@router.post("", response_model=S.BackupOut, status_code=201)
async def create_backup(files: list[UploadFile] = File(...), paths: list[str] = Form(...),
                        db: Session = Depends(get_session)):
    """Store every file read off the drive. `paths[i]` is where `files[i]` sits on the
    drive, relative to its top level; the upload's own filename is only its basename."""
    if len(paths) != len(files):
        raise HTTPException(400, "Each file needs its path on the drive")
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"That folder has {len(files)} files; a QuadStick drive has "
                                 f"far fewer. Pick the QuadStick drive itself")
    kept: dict[str, bytes] = {}
    seen: set[str] = set()      # the drive is FAT, so two names that differ only in case clash
    total = 0
    for upload, raw in zip(files, paths):
        path = clean_path(raw)
        if path is None:
            continue
        if path.lower() in seen:
            raise HTTPException(400, f"'{raw}' is in the upload twice")
        seen.add(path.lower())
        data = await read_capped(upload)
        total += len(data)
        if total > settings.max_backup_bytes:
            raise HTTPException(413, f"Those files add up to more than "
                                     f"{settings.max_backup_bytes // (1024 * 1024)} MB; a QuadStick drive "
                                     f"holds far less. Pick the QuadStick drive itself")
        kept[path] = data
    if not any(p.lower().endswith(".csv") and "/" not in p for p in kept):
        raise HTTPException(422, "That folder has no .csv profiles at its top level, so it is not "
                                 "the QuadStick drive. Nothing was saved")
    backup = M.DriveBackup(created_at=datetime.now(timezone.utc),
                           files=[M.DriveBackupFile(path=p, size=len(d), data=d) for p, d in kept.items()])
    db.add(backup)
    db.commit()
    return _out(backup, sorted((p, len(d)) for p, d in kept.items()))


@router.get("/{backup_id}/download.zip")
def download_backup(backup_id: int,
                    filename: str | None = Query(None, description="the .zip name; the browser names it "
                                                                    "in its own time zone"),
                    db: Session = Depends(get_session)):
    """The backup as one .zip whose top level is the drive's top level. Also written
    to the exports/ share, like every export."""
    b = _get(db, backup_id)
    created = _utc(b.created_at)
    name = filename or f"quadstick-backup-{created:%Y-%m-%d-%H%M}.zip"
    if not ZIP_NAME.fullmatch(name):
        raise HTTPException(400, "The filename must be letters, digits, '.', '-' or '_' and end in .zip")
    stamp = created.timetuple()[:6]

    def write(tmp: str):
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in b.files:
                z.writestr(zipfile.ZipInfo(f.path, date_time=stamp), f.data,
                           compress_type=zipfile.ZIP_DEFLATED)

    out = _export_target(name)
    data = write_atomically(out, write)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "X-Export-Path": export_path_header(out)})


@router.delete("/{backup_id}", status_code=204)
def delete_backup(backup_id: int, db: Session = Depends(get_session)):
    db.delete(_get(db, backup_id))
    db.commit()
    return Response(status_code=204)
