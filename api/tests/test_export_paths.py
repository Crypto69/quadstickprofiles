"""C5: the export filename and `csv_filename` are device filenames, never paths.
An export may only ever write directly inside the exports directory."""
from pathlib import Path
from urllib.parse import unquote
import pytest
from qsprofile.catalog import check_csv_filename, csv_filename_for_name
from conftest import FIXTURES, upload


def _exports(tmp_path):
    return tmp_path / "exports"


def _files_outside_exports(tmp_path):
    """Everything under the test's tmp dir that is not inside exports/ or the sqlite db."""
    ex = _exports(tmp_path).resolve()
    return sorted(str(p) for p in tmp_path.rglob("*")
                  if p.is_file() and ex not in p.resolve().parents and p.resolve() != ex)


@pytest.mark.parametrize("bad", ["../evil.csv", "../../evil.csv", "sub/evil.csv", "..\\evil.csv"])
def test_export_with_a_relative_path_is_refused_and_writes_nothing(client, tmp_path, bad):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    before = _files_outside_exports(tmp_path)
    r = client.get(f"/profiles/{p['id']}/export.csv", params={"filename": bad})
    assert r.status_code == 400, r.text
    assert "X-Export-Path" not in r.headers
    assert _files_outside_exports(tmp_path) == before
    assert not (tmp_path / "evil.csv").exists() and not (tmp_path.parent / "evil.csv").exists()
    assert not _exports(tmp_path).exists() or not list(_exports(tmp_path).rglob("evil.csv"))


def test_export_with_an_absolute_path_is_refused(client, tmp_path):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    target = tmp_path / "abs.csv"
    r = client.get(f"/profiles/{p['id']}/export.csv", params={"filename": str(target)})
    assert r.status_code == 400, r.text
    assert not target.exists()
    r = client.get(f"/profiles/{p['id']}/export.xlsx", params={"filename": str(target)})
    assert r.status_code == 400, r.text


def test_export_path_header_stays_inside_the_exports_directory(client, tmp_path):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    for ext, name in (("csv", "fortnite2.csv"), ("xlsx", "fortnite2.xlsx")):
        r = client.get(f"/profiles/{p['id']}/export.{ext}", params={"filename": "fortnite2.csv"})
        assert r.status_code == 200, r.text
        # W3: the header is percent-encoded UTF-8, because header values are Latin-1.
        shown = Path(unquote(r.headers["X-Export-Path"])).resolve()
        assert shown.parent == _exports(tmp_path).resolve() and shown.name == name
        assert shown.read_bytes() == r.content


def test_export_filename_breaking_the_device_rule_is_a_422(client):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    for bad in ("bad name.csv", "has,comma.csv", "a" * 28 + ".csv", "nodotcsv", ".hidden.csv"):
        r = client.get(f"/profiles/{p['id']}/export.csv", params={"filename": bad})
        assert r.status_code == 422, (bad, r.text)


def test_export_uses_the_case_the_user_typed_and_the_device_rule_allows_it(client, tmp_path):
    """The device lowercases names; mixed case is accepted on input, not rewritten."""
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    r = client.get(f"/profiles/{p['id']}/export.csv", params={"filename": "MyGame.CSV"})
    assert r.status_code == 200, r.text
    assert (_exports(tmp_path) / "MyGame.CSV").exists()


@pytest.mark.parametrize("bad", ["../../x.csv", "/etc/x.csv", "sub/x.csv", "a" * 28 + ".csv",
                                 ".x.csv", "x?.csv", "x*.csv", "x:y.csv", 'x"y.csv', "x|y.csv",
                                 "x<y>.csv", "bad name.csv", "has,comma.csv", "x.CSV.txt", "ünï.csv"])
def test_a_path_or_over_long_csv_filename_is_refused_everywhere_it_can_be_set(client, bad):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    assert client.patch(f"/profiles/{p['id']}", json={"csv_filename": bad}).status_code == 422, bad
    assert client.post("/profiles", json={"name": "T", "csv_filename": bad}).status_code == 422, bad
    assert client.post(f"/profiles/{p['id']}/duplicate", params={"csv_filename": bad}).status_code == 422, bad
    assert client.post(f"/profiles/{p['id']}/convert",
                       json={"target": "xbox", "csv_filename": bad}).status_code == 422, bad
    # and the stored name is untouched
    assert client.get(f"/profiles/{p['id']}").json()["csv_filename"] == "ddfortnite.csv"


def test_thirty_one_characters_is_the_longest_name_the_device_loads(client):
    ok = "a" * 27 + ".csv"            # 31 chars including .csv
    too_long = "a" * 28 + ".csv"      # 32: installs, never loads, corrupts the next slot
    assert len(ok) == 31 and len(too_long) == 32
    assert check_csv_filename(ok) is None
    assert "31" in (check_csv_filename(too_long) or "")
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    assert client.patch(f"/profiles/{p['id']}", json={"csv_filename": ok}).status_code == 200
    assert client.patch(f"/profiles/{p['id']}", json={"csv_filename": too_long}).status_code == 422
    # W2: the names the server invents for a copy or a conversion have to fit too, or
    # the copy installs and then every export of it is refused
    r = client.post(f"/profiles/{p['id']}/duplicate")
    assert r.status_code == 201, r.text
    copy = r.json()
    assert len(copy["csv_filename"]) <= 31 and copy["csv_filename"].endswith("_copy.csv")
    assert check_csv_filename(copy["csv_filename"]) is None
    assert client.get(f"/profiles/{copy['id']}/export.csv").status_code == 200

    r = client.post(f"/profiles/{p['id']}/convert", json={"target": "xbox"})
    assert r.status_code == 201, r.text
    conv = r.json()
    assert conv["suggested_csv_filename"] == conv["profile"]["csv_filename"]
    assert len(conv["profile"]["csv_filename"]) <= 31
    assert check_csv_filename(conv["profile"]["csv_filename"]) is None
    assert client.get(f"/profiles/{conv['profile']['id']}/export.csv").status_code == 200


def test_a_copy_of_a_short_name_keeps_the_whole_stem(client):
    """The cut only applies where it must: a normal name still gets `<stem>_copy.csv`.
    The default *name* is that same stem, so the two agree: the device loads by
    filename, and a name like "ddfortnite (copy)" beside ddfortnite_copy.csv is what
    made a stick full of copies impossible to tell apart."""
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    copy = client.post(f"/profiles/{p['id']}/duplicate").json()
    assert copy["csv_filename"] == "ddfortnite_copy.csv"
    assert copy["name"] == "ddfortnite_copy"
    conv = client.post(f"/profiles/{p['id']}/convert", json={"target": "xbox"}).json()
    assert conv["profile"]["csv_filename"] == "ddfortnite_xbox.csv"
    assert conv["profile"]["name"] == "ddfortnite_xbox"


def test_a_derived_name_and_filename_always_agree(client):
    """So a stick full of copies can be told apart: the name the owner reads in the
    library is the stem of the file they pick on the device. Nothing enforces this —
    the name is free text (see test_an_explicit_name_or_filename_still_wins) — it is
    only what the server invents when the owner does not say."""
    p = upload(client, FIXTURES / "cod.csv")["profile"]
    made = [client.post(f"/profiles/{p['id']}/duplicate").json(),
            client.post(f"/profiles/{p['id']}/convert", json={"target": "xbox"}).json()["profile"],
            client.post(f"/profiles/{p['id']}/convert", json={"target": "playstation"}).json()["profile"]]
    for got in made:
        assert csv_filename_for_name(got["name"]) == got["csv_filename"], got


def test_an_explicit_name_or_filename_still_wins(client):
    """Renaming stays free: the two fields are independently settable, and a name the
    owner picks that has nothing to do with the filename is correct — the device never
    reads the name — so it saves, reports nothing, and exports."""
    p = upload(client, FIXTURES / "cod.csv")["profile"]
    copy = client.post(f"/profiles/{p['id']}/duplicate",
                       params={"name": "My Loadout", "csv_filename": "loadout1.csv"}).json()
    assert copy["name"] == "My Loadout" and copy["csv_filename"] == "loadout1.csv"
    v = client.get(f"/profiles/{copy['id']}/validate").json()
    assert not [f for f in v["findings"] if "My Loadout" in f["message"]], v["findings"]
    assert v["errors"] == 0
    assert client.get(f"/profiles/{copy['id']}/export.csv").status_code == 200

    # only the name given: the filename stays the derived one, and that is allowed
    named = client.post(f"/profiles/{p['id']}/duplicate", params={"name": "Just A Name"}).json()
    assert named["name"] == "Just A Name" and named["csv_filename"] == "cod_copy.csv"
    conv = client.post(f"/profiles/{p['id']}/convert",
                       json={"target": "xbox", "csv_filename": "codx.csv"}).json()["profile"]
    assert conv["csv_filename"] == "codx.csv" and conv["name"] == "codx"


def test_the_filename_rule_in_one_place():
    for good in ("ddfortnite.csv", "cod.csv", "My_Game-2.csv", "a.b.csv", "X.CSV"):
        assert check_csv_filename(good) is None, good
    for bad, word in (("", "empty"), ("../x.csv", "/"), ("x y.csv", "whitespace"),
                      (".x.csv", "dot"), ("x.txt", ".csv"), ("ü.csv", "ASCII"),
                      ("x,y.csv", "comma"), ("x+y.csv", "letters, digits")):
        msg = check_csv_filename(bad)
        assert msg and word in msg, (bad, msg)
