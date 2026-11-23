"""Runtime settings, all overridable from the environment / .env.

The desktop launcher (desktop/launcher.py) sets every QS_* variable it needs and
QS_NO_DOTENV=1 before importing this module: `.env` is looked up relative to the
process's working directory, which for a double-clicked app is anywhere."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QS_", extra="ignore",
                                      env_file=None if os.getenv("QS_NO_DOTENV") else ".env")

    # Required, no default: a default would have to carry a password, and the
    # one this repo used to ship (quadstick/quadstick) is public. Docker
    # compose sets it from QS_DB_PASSWORD; the desktop launcher sets it to its
    # SQLite file; a local run sets it in .env or the environment.
    database_url: str
    exports_dir: Path = REPO_ROOT / "exports"      # also an SMB share on the NAS later
    fixtures_dir: Path = REPO_ROOT / "fixtures"
    actions_dir: Path = REPO_ROOT / "actions"
    # The built web app (web/dist). Set only by the desktop build: this process then
    # serves the SPA itself (app/spa.py). On the NAS nginx does it and this stays None.
    static_dir: Path | None = None
    # Biggest upload an import will read (QS_MAX_UPLOAD_BYTES). A device .csv is a few
    # KB and the largest .xlsx fixture ~61 KB, but a Google Sheet somebody pasted
    # screenshots into downloads as several MB: of 131 community workbooks tried on
    # 2026-11-23, four were over the old 2 MB cap and the largest was 6.4 MB.
    # nginx caps /api/ at the same size, but the API is also published unproxied
    # (docker-compose 8325) and the desktop build has no proxy at all.
    max_upload_bytes: int = 8 * 1024 * 1024
    # Biggest whole-drive backup (QS_MAX_BACKUP_BYTES). Each file is still capped at
    # max_upload_bytes; the drive holds .csv profiles and joystick.bin (the firmware
    # deletes everything else at boot), so 20 MB is far more than a full stick.
    # web/nginx.conf allows the same on POST /api/backups.
    max_backup_bytes: int = 20 * 1024 * 1024


settings = Settings()
