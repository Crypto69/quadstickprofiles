"""FastAPI app. Everything is mounted under /api so the web container can serve
the SPA at / and reverse-proxy /api to this service without a path rewrite."""
import os
from importlib.metadata import PackageNotFoundError, version as _package_version

from fastapi import APIRouter, FastAPI
from .routers import catalog, prefs, profiles
from .settings import settings

API_PREFIX = "/api"

try:                                    # api/pyproject.toml is the one place this number lives
    API_VERSION = _package_version("qsapi")
except PackageNotFoundError:            # running from a checkout without `pip install -e api`
    API_VERSION = "dev"

app = FastAPI(title="QuadStick Profile Studio API", version=API_VERSION,
              openapi_url=f"{API_PREFIX}/openapi.json", docs_url=f"{API_PREFIX}/docs",
              redoc_url=None,
              description="Wraps core/qsprofile: catalog, profiles, import/export, validation, "
                          "console conversion and printable reference cards.")

api = APIRouter(prefix=API_PREFIX)
api.include_router(catalog.router)
api.include_router(profiles.router)
api.include_router(prefs.router)


@api.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@api.get("/version", tags=["meta"])
def version():
    """What is actually running. deploy.sh stamps the image with the commit it
    built, so this is the answer to \"did my deploy land?\"."""
    return {"version": app.version,
            # the readable deploy number (1.0, 1.1 ...) computed by deploy.sh
            "app_version": os.getenv("QS_APP_VERSION", "dev"),
            "commit": os.getenv("QS_GIT_SHA", "unknown"),
            "built": os.getenv("QS_BUILD_TIME", "unknown")}


app.include_router(api)


@app.get("/health", tags=["meta"], include_in_schema=False)
def health_root():
    """Kept unprefixed for the Docker health check and the NAS reverse proxy."""
    return {"status": "ok"}


# Desktop build only: serve web/dist from this process. Must come last so /api/* and
# /health above keep winning over the SPA catch-all.
if settings.static_dir:
    from .spa import mount_spa
    mount_spa(app, settings.static_dir)
