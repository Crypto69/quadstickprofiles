"""C5: the export filename and `csv_filename` are device filenames, never paths.
An export may only ever write directly inside the exports directory."""
import pytest
from qsprofile.catalog import check_csv_filename
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
        from pathlib import Path
        shown = Path(r.headers["X-Export-Path"]).resolve()
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


def test_the_filename_rule_in_one_place():
    for good in ("ddfortnite.csv", "cod.csv", "My_Game-2.csv", "a.b.csv", "X.CSV"):
        assert check_csv_filename(good) is None, good
    for bad, word in (("", "empty"), ("../x.csv", "/"), ("x y.csv", "whitespace"),
                      (".x.csv", "dot"), ("x.txt", ".csv"), ("ü.csv", "ASCII"),
                      ("x,y.csv", "comma"), ("x+y.csv", "letters, digits")):
        msg = check_csv_filename(bad)
        assert msg and word in msg, (bad, msg)
