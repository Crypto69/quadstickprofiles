"""Reading an uploaded file without trusting its size (W7).

`await file.read()` with no argument buffers the whole body in memory. nginx caps
`/api/` at 2 MB, but both compose files also publish the API directly on 8325 with
no proxy in front of it, and the desktop build runs uvicorn on its own — so the cap
has to live here as well.

Starlette has already spooled the multipart part to a temporary file by the time a
handler runs, so this is a memory cap, not a wire-level one; refusing at the socket
would need ASGI middleware and is out of scope.
"""
from fastapi import HTTPException, UploadFile

from .settings import settings

CHUNK = 64 * 1024


def _too_big(file: UploadFile, limit: int) -> HTTPException:
    name = file.filename or "the upload"
    return HTTPException(413, f"{name} is larger than {limit // 1024} KB; "
                              f"a QuadStick profile is a few KB")


async def read_capped(file: UploadFile, limit: int | None = None,
                      chunk: int = CHUNK) -> bytes:
    """All the bytes of `file`, or a 413 as soon as they exceed `limit`.

    `limit` defaults to `settings.max_upload_bytes`, read at call time so a test
    (or QS_MAX_UPLOAD_BYTES) can monkeypatch it. `UploadFile.size` is a hint from
    the multipart parser: when it is present and already over the limit the body
    is refused without reading any of it; otherwise the chunk loop catches it.
    """
    limit = settings.max_upload_bytes if limit is None else limit
    if file.size is not None and file.size > limit:
        raise _too_big(file, limit)
    buf = bytearray()
    while part := await file.read(chunk):
        buf += part
        if len(buf) > limit:
            raise _too_big(file, limit)
    return bytes(buf)
