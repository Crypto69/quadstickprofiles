"""Response header values that have to survive a non-Latin-1 filesystem path (W3).

HTTP header values are encoded Latin-1, so `{"X-Export-Path": str(out)}` raises
`UnicodeEncodeError` inside Starlette — *after* the export has already been written
and `os.replace`d into place, turning a successful export into a 500. Latin-1 covers
accented Western European letters (é, ü), so the break needs a path containing
something outside it: ł, ř, Cyrillic, CJK, an emoji. The desktop build exports under
`Path.home()/"Documents"`, i.e. under the user's account name, so this is reachable.

Plain percent-encoding, not strict RFC 8187 (owner call, 2026-09-15): an ASCII path
is unchanged byte-for-byte and `web/src/api/client.ts` decodes with one
`decodeURIComponent`.
"""
from pathlib import Path
from urllib.parse import quote


def export_path_header(out: Path | str) -> str:
    """`str(out)` as a header-safe, UTF-8 percent-encoded value.

    Separators stay literal so the value is still readable as a path; everything
    outside the unreserved set — including the `%` of any literal percent in a
    filename — is escaped, which is what makes the client's single
    `decodeURIComponent` exact.
    """
    return quote(str(out), safe="/\\:")
