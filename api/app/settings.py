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

    database_url: str = "postgresql+psycopg://quadstick:quadstick@localhost:5432/quadstick"
    exports_dir: Path = REPO_ROOT / "exports"      # also an SMB share on the NAS later
    fixtures_dir: Path = REPO_ROOT / "fixtures"
    actions_dir: Path = REPO_ROOT / "actions"
    # The built web app (web/dist). Set only by the desktop build: this process then
    # serves the SPA itself (app/spa.py). On the NAS nginx does it and this stays None.
    static_dir: Path | None = None


settings = Settings()
