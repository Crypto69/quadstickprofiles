"""Serve the built web app (web/dist) from this process.

Only the desktop build uses this (settings.static_dir / QS_STATIC_DIR); on the NAS
nginx serves the files and proxies /api. It replicates what web/nginx.conf does:
hashed files under /assets/ are immutable, an unknown asset is a 404, and every
other path is an app route (history-mode router), so it gets index.html."""
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"

# Windows reads MIME types from the registry, which can call .js "text/plain" and
# not know .woff2 at all; a module script with the wrong type does not run.
for ext, mime in ((".js", "text/javascript"), (".mjs", "text/javascript"),
                  (".css", "text/css"), (".woff2", "font/woff2"), (".webp", "image/webp")):
    mimetypes.add_type(mime, ext)


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Call after every API route is registered: the catch-all below must lose to
    /api/* and /health, and Starlette matches routes in registration order."""
    root = Path(static_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"static_dir has no index.html: {root}")

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.middleware("http")
    async def asset_cache_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = IMMUTABLE
        return response

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Not found")    # an unknown API path is not an app route
        if path:
            candidate = (root / path).resolve()
            if root in candidate.parents and candidate.is_file():    # favicon.ico, robots.txt
                return FileResponse(candidate, headers={"Cache-Control": NO_CACHE})
        return FileResponse(index, headers={"Cache-Control": NO_CACHE})
