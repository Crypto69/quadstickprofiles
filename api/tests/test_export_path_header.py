"""W3: `X-Export-Path` must survive a path HTTP headers cannot spell.

Header values are encoded Latin-1, so a raw `str(out)` is a `UnicodeEncodeError`
inside Starlette — after the file has already been written and moved into place,
turning a good export into a 500. Latin-1 does cover é and ü; what breaks it is
ł, ř, Cyrillic, CJK, an emoji. The desktop build exports under the user's
Documents folder, so the account name reaches this.

`export_path_header` is tested here directly, and end-to-end through both export
routes, which now set the encoded form.
"""
from pathlib import Path
from urllib.parse import unquote

import pytest

from app.headers import export_path_header
from app.settings import settings

from conftest import FIXTURES, upload


# --------------------------------------------------------------- the helper

def test_an_ascii_path_is_unchanged_byte_for_byte():
    """The common case must not churn: everything already shipped keeps working."""
    assert export_path_header(Path("/app/exports/ddfortnite.csv")) == "/app/exports/ddfortnite.csv"


@pytest.mark.parametrize("name", ["Łukasz", "Řehoř", "Иван", "山田", "🎮"])
def test_a_path_outside_latin_1_encodes_to_ascii_and_decodes_back(name):
    raw = Path(f"/Users/{name}/Documents/QuadStick/exports/ddfortnite.csv")
    header = export_path_header(raw)
    assert header.isascii(), header
    header.encode("latin-1")                      # what Starlette does; must not raise
    assert Path(unquote(header)) == raw


def test_a_latin_1_path_is_still_encoded_so_one_decode_is_always_right():
    """é would survive Latin-1, but encoding it too means the client has exactly one
    rule instead of a guess."""
    header = export_path_header(Path("/Users/José/exports/x.csv"))
    assert header.isascii()
    assert unquote(header) == "/Users/José/exports/x.csv"


def test_a_literal_percent_in_a_name_round_trips():
    """The failure mode of percent-encoding: a real `%` must be escaped, or the
    client's decodeURIComponent would eat it."""
    raw = Path("/app/exports/100%_done.csv")
    assert unquote(export_path_header(raw)) == str(raw)


def test_separators_stay_readable():
    assert "/" in export_path_header(Path("/app/exports/x.csv"))
    assert export_path_header("C:\\Users\\x\\exports\\y.csv").startswith("C:\\Users")


# --------------------------------------------------------------- end to end

def test_exports_under_a_non_latin_1_directory_succeed(client, tmp_path, monkeypatch):
    # A real fixture, not a bare profile: export is refused while validation errors
    # exist, and a profile with no modes has them, so a bare one never reaches the header.
    monkeypatch.setattr(settings, "exports_dir", tmp_path / "Łukasz" / "exports")
    pid = upload(client, FIXTURES / "ddfortnite.csv")["profile"]["id"]
    # /prefs/export.csv is a 409 until there is something to write.
    assert client.put("/prefs", json={"preferences": {"volume": "40"}}).status_code == 200
    for path in (f"/profiles/{pid}/export.csv", f"/profiles/{pid}/export.xlsx",
                 "/prefs/export.csv"):
        r = client.get(path)
        assert r.status_code == 200, (path, r.text)
        header = r.headers["X-Export-Path"]
        assert header.isascii(), (path, header)
        assert Path(unquote(header)).exists(), path
