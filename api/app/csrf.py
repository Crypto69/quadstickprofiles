"""Same-origin guard for the state-changing API routes (W8).

The app is single-user with no login (decided 2026-09-15), so there is no session
cookie to steal — but the API is reachable from the LAN (docker-compose publishes
it on 8325 unproxied, the desktop build runs uvicorn directly) and a multipart
`POST /api/profiles/import` is a "simple" request: any web page the owner happens
to open can submit a hidden form at it with no CORS preflight to stop it.

Two layers, both cheap:

1. **Origin check.** When the browser sends an `Origin` header, its hostname must
   match the hostname the request was addressed to. Compare *hostnames only*:
   nginx forwards `$host` without the port (web/nginx.conf), so the API sees
   `Host: nas` while the browser sends `Origin: http://nas:8324`. `Origin: null`
   (a sandboxed iframe, a `file://` page) is refused outright.
2. **`X-Requested-With`.** A custom header cannot be set by a form post or an
   `<img>`/`<script>` tag, so requiring one blocks the whole simple-request class
   even from a caller that sends no `Origin` at all. The SPA sets it in
   `web/src/api/client.ts`; the test suite sets it in `api/tests/conftest.py`.

Layer 2 means a bare `curl -X POST` is refused until it adds
`-H "X-Requested-With: QuadStickProfileStudio"`. That is the intended trade
(owner call, 2026-09-15: both layers). Safe methods are never touched, so every
GET — including the card, the summary and the exports — is unaffected.
"""
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

#: Methods that do not change state, so they need no guard.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

#: The value the SPA (and the tests) send in `X-Requested-With`. Not a secret and
#: not a token: its only job is to be a *custom* header, which a cross-origin form
#: post cannot set without a CORS preflight the API never answers.
REQUESTED_WITH = "QuadStickProfileStudio"

HEADER = "X-Requested-With"


def _hostname(value: str | None) -> str | None:
    """The host part of an `Origin` or a `Host` header, with any port dropped.

    `Origin` is a full origin (`http://nas:8324`); `Host` is bare (`nas:8324`, or
    just `nas` once nginx has forwarded `$host`). `urlsplit` only finds a hostname
    after a scheme or a `//`, so add one when it is missing."""
    if not value:
        return None
    return urlsplit(value if "://" in value else f"//{value}").hostname


def _refuse(detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=403)


def install_csrf_guard(app: FastAPI, api_prefix: str) -> None:
    """Register the guard on `app` for every mutating request under `api_prefix`."""

    @app.middleware("http")
    async def same_origin_guard(request: Request, call_next):
        if request.method not in SAFE_METHODS and request.url.path.startswith(api_prefix):
            origin = request.headers.get("origin")
            if origin is not None:
                # "null" is what a sandboxed iframe or a file:// page sends.
                if origin == "null" or _hostname(origin) != _hostname(request.headers.get("host")):
                    return _refuse("Cross-origin request refused")
            if request.headers.get(HEADER) != REQUESTED_WITH:
                return _refuse(f"Missing {HEADER}: {REQUESTED_WITH}")
        return await call_next(request)
