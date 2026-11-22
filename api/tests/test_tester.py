"""The tester's two endpoints: the page's spec and the qstest profile, both from
core/qsprofile/tester.py."""
from urllib.parse import unquote
from qsprofile import tester

from conftest import FIXTURES


def test_spec_is_the_core_table(client):
    r = client.get("/tester/spec")
    assert r.status_code == 200
    assert r.json() == tester.spec()
    assert [m["hat"] for m in r.json()["modes"]] == [0, 2, 4, 6, 1]


def test_qstest_csv_is_the_device_file_and_lands_in_exports(client, tmp_path):
    r = client.get("/tester/qstest.csv")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="qstest.csv"'
    assert r.content == (FIXTURES / "qstest.csv").read_bytes() + b"\r\n"
    written = tmp_path / "exports" / "qstest.csv"
    assert written.read_bytes() == r.content
    assert unquote(r.headers["x-export-path"]) == str(written.resolve())
