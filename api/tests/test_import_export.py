"""Import -> DB -> export must be byte-identical to the device files, exactly as
tests/test_roundtrip.py proves for the core package, but through the API."""
import pytest
from qsprofile import load
from conftest import FIXTURES, upload


@pytest.mark.parametrize("name", ["ddfortnite.csv", "cod.csv"])
def test_device_csv_import_export_is_identical(client, name):
    p = upload(client, FIXTURES / name)["profile"]
    r = client.get(f"/profiles/{p['id']}/export.csv")
    assert r.status_code == 200, r.text
    assert r.content == (FIXTURES / name).read_bytes()
    assert r.headers["content-disposition"].endswith(f'"{name}"')


@pytest.mark.parametrize("xlsx,csvname,title", [
    ("ddfortnite.xlsx", "ddfortnite.csv", "ddfortnite"),
    ("Call_of_Duty.xlsx", "cod.csv", "Call of Duty"),
])
def test_google_sheet_xlsx_import_exports_the_addon_bytes(client, xlsx, csvname, title):
    real, _ = load(str(FIXTURES / csvname))
    p = upload(client, FIXTURES / xlsx)["profile"]
    # the sheet download carries neither the sheet URL nor its title; the user sets them
    r = client.patch(f"/profiles/{p['id']}", json={"name": title, "source_url": real.source_url})
    assert r.status_code == 200, r.text
    r = client.get(f"/profiles/{p['id']}/export.csv")
    assert r.status_code == 200, r.text
    assert r.content == (FIXTURES / csvname).read_bytes()


def test_export_writes_a_copy_into_the_exports_share(client, tmp_path):
    p = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    r = client.get(f"/profiles/{p['id']}/export.csv", params={"filename": "fortnite2.csv"})
    assert r.status_code == 200
    saved = tmp_path / "exports" / "fortnite2.csv"
    assert saved.read_bytes() == r.content
    assert r.content.startswith(b"QuadStick Configuration,Version 1.4,")
    assert b"\r\nfortnite2.csv,,Normal,\r\n" in r.content


def test_xlsx_export_reimports_to_the_same_mappings(client):
    p = upload(client, FIXTURES / "Call_of_Duty_Advanced_Warfare_XBox_One.xlsx")["profile"]
    assert p["console"] == "xbox"
    r = client.get(f"/profiles/{p['id']}/export.xlsx")
    assert r.status_code == 200
    import io, tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "x.xlsx"
        out.write_bytes(r.content)
        again, _ = load(str(out))
    assert again.console == "xbox"
    assert [(m.output, m.function, m.params, m.inputs) for md in again.modes for m in md.mappings] == \
           [(m["output"], m["function"], m["params"], m["inputs"]) for md in p["modes"] for m in md["mappings"]]


def test_export_is_refused_while_validation_errors_exist(client):
    r = client.post("/profiles", json={"name": "Empty", "csv_filename": "empty.csv"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    v = client.get(f"/profiles/{pid}/validate").json()
    assert v["errors"] >= 1 and any("No mode sheets" in f["message"] for f in v["findings"])
    for ext in ("csv", "xlsx"):
        r = client.get(f"/profiles/{pid}/export.{ext}")
        assert r.status_code == 409
        assert r.json()["detail"]["validation"]["errors"] >= 1
    r = client.post(f"/profiles/{pid}/convert", json={"target": "xbox"})
    assert r.status_code == 409


def test_import_reports_the_known_fortnite_warnings(client):
    findings = upload(client, FIXTURES / "ddfortnite.xlsx")["findings"]
    msgs = [f["message"] for f in findings["findings"] if f["severity"] == "warning"]
    assert any("destiny.csv" in m for m in msgs)            # stale Reference Card sheet (import-time only)
    # An input that fires an action and changes mode at once is a design, not a
    # fault: it is described in the notes, never listed as something to fix.
    notes = [f["message"] for f in findings["findings"] if f["severity"] == "info"]
    assert any("mp_center_sip" in m and "increment_mode" in m for m in notes)
    assert not any("at the same moment" in m for m in msgs)
    assert findings["errors"] == 0


def test_import_rejects_other_file_types(client, tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("hello")
    with open(bad, "rb") as f:
        r = client.post("/profiles/import", files={"file": ("x.txt", f)})
    assert r.status_code == 415


# ---------------------------------------------------------------- C6: store what core accepts
def _mode_block(n, label="M", channel="usb", rows=("increment_mode,normal,right_sip,",
                                                    "left_joy_up,normal,up,"), filename="m.csv"):
    head = [f"Profile Name,,{label},", f"{filename if n == 1 else ''},,Normal,",
            f"Output or Function,Function,{channel},"]
    return "\r\n".join(head + list(rows)) + "\r\n\r\n"


def _csv(tmp_path, name, body, title="T", prefs=()):
    text = (f"QuadStick Configuration,Version 1.4,,{title}\r\n" + body
            + "Preferences,\r\n,,,,\r\nPreference,Value,Units,Description,\r\n"
            + "".join(f"{row}\r\n" for row in prefs) + "\r\n")
    p = tmp_path / name
    p.write_bytes(text.encode("ascii"))
    return p


def _post(client, path):
    with open(path, "rb") as f:
        return client.post("/profiles/import", files={"file": (path.name, f)})


def test_import_of_content_the_input_schema_rejects_reads_back_and_exports(client, tmp_path):
    """A 40-character C1 label, C3 = both and a blank title are all legal on the
    device and in core. They used to commit and then 500 on every GET because the
    response model inherited the input rules."""
    label = "A" * 40
    src = _csv(tmp_path, "m.csv", _mode_block(1, label=label, channel="both"), title="")
    r = _post(client, src)
    assert r.status_code == 201, r.text
    p = r.json()["profile"]
    assert p["name"] == "" and p["modes"][0]["name"] == label and p["modes"][0]["channel"] == "both"
    r = client.get(f"/profiles/{p['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["modes"][0]["label"] == label
    assert client.get("/profiles").status_code == 200
    r = client.get(f"/profiles/{p['id']}/export.csv")
    assert r.status_code == 200, r.text
    assert r.content == src.read_bytes()


# files the input rules used to refuse on the way back in (R1): what the import
# stored must PUT back and live-check, with core's finding, not a 422
ODD_FILES = {
    "bad_params": dict(rows=("increment_mode,normal,right_sip,", "x,repeat five 2000,lip,",
                             "left_joy_up,normal,up,")),
    "too_many_params": dict(rows=("increment_mode,normal,right_sip,", "x,repeat 1 2 3,lip,",
                                  "left_joy_up,normal,up,")),
    "long_label": dict(label="A" * 40),
    "blank_title": dict(title=""),
}


def _odd_file(tmp_path, key):
    spec = dict(ODD_FILES[key])
    title = spec.pop("title", "T")
    return _csv(tmp_path, "m.csv", _mode_block(1, **spec), title=title)


def _content(doc):
    """A profile document without what a save legitimately changes: a PUT replaces
    the children, so every mode and mapping gets a new id (Postgres sequences never
    reuse one; SQLite happens to), and updated_at moves."""
    if isinstance(doc, dict):
        return {k: _content(v) for k, v in doc.items() if k not in ("id", "updated_at")}
    if isinstance(doc, list):
        return [_content(v) for v in doc]
    return doc


@pytest.mark.parametrize("name", ["ddfortnite.csv", "cod.csv", "synthetic_pref_override.csv", *ODD_FILES])
def test_get_put_export_is_byte_identical_for_every_csv_fixture(client, tmp_path, name):
    """The editor's save path: what GET returns can be PUT back unchanged — for the
    fixtures and for the files whose rows core keeps but the input rules used to 422."""
    src = FIXTURES / name if name.endswith(".csv") else _odd_file(tmp_path, name)
    p = upload(client, src)["profile"]
    doc = client.get(f"/profiles/{p['id']}").json()
    r = client.put(f"/profiles/{p['id']}", json=doc)
    assert r.status_code == 200, r.text
    assert _content(client.get(f"/profiles/{p['id']}").json()) == _content(doc)
    r = client.get(f"/profiles/{p['id']}/export.csv")
    if name.endswith("params"):                 # the row error still keeps it off the stick
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["validation"]["errors"] >= 1
    else:
        assert r.status_code == 200, r.text
        assert r.content == src.read_bytes()


@pytest.mark.parametrize("key, error", [("bad_params", "whole numbers"), ("too_many_params", "at most 2 parameter")])
def test_an_imported_bad_row_is_live_checked_with_its_finding_not_a_422(client, tmp_path, key, error):
    """R1: import stores `repeat five 2000` (201, the row error, export 409). The
    editor then PUTs the document GET returned and live-checks it on every change;
    both used to be 422 `int_parsing`, which the editor can only show as "request
    failed". Now the same row-anchored error comes back from the live check, the
    save goes through, and export is still refused."""
    r = _post(client, _odd_file(tmp_path, key))
    assert r.status_code == 201, r.text
    pid = r.json()["profile"]["id"]
    doc = client.get(f"/profiles/{pid}").json()
    v = client.post("/profiles/validate", json=doc)
    assert v.status_code == 200, v.text
    hits = [f for f in v.json()["findings"] if error in f["message"]]
    assert hits and hits[0]["severity"] == "error" and hits[0]["mode"] == 1 and hits[0]["row"] == 5
    assert v.json()["findings"] == client.get(f"/profiles/{pid}/validate").json()["findings"]
    assert client.put(f"/profiles/{pid}", json=doc).status_code == 200
    assert client.get(f"/profiles/{pid}/export.csv").status_code == 409
    # the rules that stay 422s: an unknown function name (FK) and the text rule
    doc["modes"][0]["mappings"][1]["function"] = "hold"
    assert client.put(f"/profiles/{pid}", json=doc).status_code == 422
    doc["modes"][0]["mappings"][1]["function"] = "repeat"
    doc["modes"][0]["name"] = "Left, right"
    assert client.put(f"/profiles/{pid}", json=doc).status_code == 422


def test_a_long_label_and_a_blank_title_save_and_live_check(client, tmp_path):
    """The other two shapes the input rules used to refuse: a 40-character C1 (it
    becomes the mode name, which had a 31-character cap) and a blank title
    (`name` had min_length=1). Both are legal on the device and in core."""
    for key in ("long_label", "blank_title"):
        pid = _post(client, _odd_file(tmp_path, key)).json()["profile"]["id"]
        doc = client.get(f"/profiles/{pid}").json()
        r = client.post("/profiles/validate", json=doc)
        assert r.status_code == 200, (key, r.text)
        assert r.json()["errors"] == 0, (key, r.json()["findings"])
        assert client.put(f"/profiles/{pid}", json=doc).status_code == 200, key
        # a name the user has just cleared in the editor is checked, not refused
        doc["modes"][0]["name"] = ""
        assert client.post("/profiles/validate", json=doc).status_code == 200, key


def test_the_import_name_override_follows_the_line_1_rule(client, tmp_path):
    """R2: the `name` form field is typed, not read from the file, and used to skip the
    text check: a line break in it imported with 0 errors and then GET /validate showed
    1. It now follows the JSON bodies' line-1 rule — a line break or non-ASCII is a 422
    before anything is stored, a comma only warns — and the import's findings are
    computed on the name that is stored, so they match GET /validate."""
    src = _csv(tmp_path, "m.csv", _mode_block(1))
    for bad in ("Call of\nDuty", "Dut\u00fd"):
        with open(src, "rb") as f:
            r = client.post("/profiles/import", files={"file": ("m.csv", f)}, data={"name": bad})
        assert r.status_code == 422, (bad, r.text)
        assert "name" in r.json()["detail"]
    assert client.get("/profiles").json() == []
    with open(src, "rb") as f:
        r = client.post("/profiles/import", files={"file": ("m.csv", f)}, data={"name": "Call, of Duty"})
    assert r.status_code == 201, r.text
    got = r.json()
    assert got["profile"]["name"] == "Call, of Duty"
    stored = client.get(f"/profiles/{got['profile']['id']}/validate").json()
    assert got["findings"]["findings"] == stored["findings"]
    assert got["findings"]["errors"] == stored["errors"] == 0
    assert any("comma" in f["message"] and f["row"] == 1 for f in stored["findings"])


def test_seventeen_modes_are_refused_on_import_with_the_rule_6_error(client, tmp_path):
    """The modes table cannot hold position 17, so the import is refused up front with
    the core finding rather than half-committed."""
    body = "".join(_mode_block(n, label=f"M{n}") for n in range(1, 18))
    r = _post(client, _csv(tmp_path, "m.csv", body))
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "Import refused" in detail["message"] and "17 modes" in detail["message"]
    assert any("at most 16" in f["message"] and f["severity"] == "error"
               for f in detail["validation"]["findings"])
    assert client.get("/profiles").json() == []


def test_import_keeps_a_bad_function_cell_and_blocks_export(client, tmp_path):
    """`repeat five 2000` is what the file says, so the import stores it verbatim
    (the row can be shown and fixed here) and the validator's error keeps it off
    the stick: the firmware would read 'five' as 0."""
    rows = ("increment_mode,normal,right_sip,", "x,repeat five 2000,lip,", "left_joy_up,normal,up,")
    r = _post(client, _csv(tmp_path, "m.csv", _mode_block(1, rows=rows)))
    assert r.status_code == 201, r.text
    pid = r.json()["profile"]["id"]
    assert any("whole numbers" in f["message"] and f["severity"] == "error"
               for f in r.json()["findings"]["findings"])
    row = client.get(f"/profiles/{pid}").json()["modes"][0]["mappings"][1]
    assert row["function"] == "repeat" and row["params"] == ["five", 2000]
    v = client.get(f"/profiles/{pid}/validate").json()
    assert v["errors"] >= 1
    assert any("whole numbers" in f["message"] and f["mode"] == 1 and f["row"] == 5 for f in v["findings"])
    r = client.get(f"/profiles/{pid}/export.csv")
    assert r.status_code == 409
    assert r.json()["detail"]["validation"]["errors"] >= 1


def test_unknown_function_name_is_refused_on_import(client, tmp_path):
    """`mappings.function` is a foreign key to function_catalog, so an unknown name
    has nowhere to go; the file's own error comes back with the refusal."""
    rows = ("increment_mode,normal,right_sip,", "x,hold 5,lip,", "left_joy_up,normal,up,")
    r = _post(client, _csv(tmp_path, "m.csv", _mode_block(1, rows=rows)))
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "hold" in detail["message"]
    assert detail["validation"]["errors"] >= 1
    assert client.get("/profiles").json() == []


def test_a_bad_a2_filename_is_refused_on_import_with_the_rule_1_error(client, tmp_path):
    """The profiles table has a CHECK on csv_filename (on Postgres); the API applies the
    same rule everywhere so SQLite and Postgres behave alike."""
    text = ("QuadStick Configuration,Version 1.4,,T\r\nProfile Name,,M,\r\n../evil.csv,,Normal,\r\n"
            "Output or Function,Function,usb,\r\nincrement_mode,normal,right_sip,\r\n\r\n"
            "Preferences,\r\n,,,,\r\nPreference,Value,Units,Description,\r\n\r\n")
    src = tmp_path / "m.csv"
    src.write_bytes(text.encode())
    r = _post(client, src)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "A2" in detail["message"]
    assert client.get("/profiles").json() == []


def test_an_empty_function_cell_and_an_override_rows_column_b_round_trip(client, tmp_path):
    """Two cells the table used to rewrite: an empty function cell became `normal`
    (the device reads it that way, but the bytes changed) and an override row's
    column B was dropped (the device ignores it, but the bytes changed). Both now
    come back out as they went in, through import and through the editor's GET -> PUT."""
    rows = ("increment_mode,normal,right_sip,", "x,,lip,", "mouse_speed,normal,120,", "left_joy_up,normal,up,")
    src = _csv(tmp_path, "m.csv", _mode_block(1, rows=rows))
    r = _post(client, src)
    assert r.status_code == 201, r.text
    pid = r.json()["profile"]["id"]
    msgs = [f["message"] for f in r.json()["findings"]["findings"]]
    assert any("no function" in m for m in msgs)                       # info: read as normal
    assert any("column B" in m and "does nothing" in m for m in msgs)  # warning: B ignored
    rows_out = client.get(f"/profiles/{pid}").json()["modes"][0]["mappings"]
    assert rows_out[1]["function"] == "" and rows_out[1]["params"] == []
    assert rows_out[2]["kind"] == "preference" and rows_out[2]["function"] == "normal" \
        and rows_out[2]["value"] == "120"
    assert client.get(f"/profiles/{pid}/export.csv").content == src.read_bytes()
    doc = client.get(f"/profiles/{pid}").json()
    assert client.put(f"/profiles/{pid}", json=doc).status_code == 200
    assert client.get(f"/profiles/{pid}/export.csv").content == src.read_bytes()
    # rows the editor creates: no function given means normal; an override row's B stays empty
    body = {"name": "E", "csv_filename": "e.csv", "modes": [{"name": "M", "mappings": [
        {"output": "increment_mode", "inputs": ["right_sip"]},
        {"kind": "preference", "output": "mouse_speed", "value": "120"},
        {"output": "x", "function": "", "inputs": ["lip"]},
    ]}]}
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    csv = client.get(f"/profiles/{r.json()['id']}/export.csv").content.decode()
    assert "increment_mode,normal,right_sip," in csv and "mouse_speed,,120," in csv and "\r\nx,,lip,\r\n" in csv
    # an empty cell takes no parameters, and column B on an override row is still a cell in the file
    body["modes"][0]["mappings"][2]["params"] = [5]
    assert client.post("/profiles", json=body).status_code == 422
    body["modes"][0]["mappings"][2]["params"] = []
    body["modes"][0]["mappings"][1]["function"] = "a,b"
    assert client.post("/profiles", json=body).status_code == 422


# ---------------------------------------------------------------- C2: the file's own emulation mode
def _drive_findings(findings):
    return [f for f in findings if "hides the flash drive" in f["message"]]


def test_emulation_mode_in_the_preferences_block_triggers_the_hidden_drive_warning(client, tmp_path):
    """The device applies the enable_DS3_emulation row of the Preferences block; there
    is no other source. The row survives import and export byte for byte, the Library
    summary derives its emulation_mode from it, and the warning follows the firmware."""
    src = _csv(tmp_path, "m.csv", _mode_block(1), prefs=("enable_DS3_emulation,6,,,",))
    r = _post(client, src)
    assert r.status_code == 201, r.text
    got = r.json()
    hidden = _drive_findings(got["findings"]["findings"])
    assert hidden and hidden[0]["severity"] == "warning" and "firmware 2373" in hidden[0]["message"]
    pid = got["profile"]["id"]
    assert got["profile"]["preferences"] == {"enable_DS3_emulation": "6"}
    assert client.get("/profiles").json()[0]["emulation_mode"] == 6
    v = client.get(f"/profiles/{pid}/validate").json()
    assert v["errors"] == 0 and _drive_findings(v["findings"])
    r = client.get(f"/profiles/{pid}/export.csv")
    assert r.status_code == 200 and r.content == src.read_bytes()
    # mode 6 hides the drive on 2373 only, so the warning follows the firmware the import names
    with open(src, "rb") as f:
        r = client.post("/profiles/import", files={"file": ("m.csv", f)}, data={"firmware": "1476"})
    assert r.status_code == 201, r.text
    assert not _drive_findings(r.json()["findings"]["findings"])
    assert client.get("/profiles").json()[0]["emulation_mode"] == 6      # derived, whatever the firmware


def test_a_mode_override_row_setting_a_hidden_drive_mode_is_warned_with_its_row(client, tmp_path):
    """A per-mode override row (A = key, C = value) can set the emulation mode for that
    mode alone; the warning names the mode and the spreadsheet row so it can be found."""
    rows = ("increment_mode,normal,right_sip,", "enable_DS3_emulation,,6,", "left_joy_up,normal,up,")
    r = _post(client, _csv(tmp_path, "m.csv", _mode_block(1, rows=rows)))
    assert r.status_code == 201, r.text
    pid = r.json()["profile"]["id"]
    override = r.json()["profile"]["modes"][0]["mappings"][1]
    assert override["kind"] == "preference" and override["output"] == "enable_DS3_emulation" \
        and override["value"] == "6" and override["row"] == 5
    hidden = _drive_findings(client.get(f"/profiles/{pid}/validate").json()["findings"])
    assert hidden and hidden[0]["severity"] == "warning"
    assert hidden[0]["mode"] == 1 and hidden[0]["row"] == 5 and "this mode only" in hidden[0]["message"]
    # the summary only derives from the profile-scope row, so a per-mode value is not shown there
    assert client.get("/profiles").json()[0]["emulation_mode"] is None


def test_hidden_drive_mode_in_default_csv_blocks_export(client, tmp_path):
    """default.csv loads at every boot, so there is no profile to switch away from: a
    drive-hiding mode there is an error and the export is refused, not warned about."""
    src = _csv(tmp_path, "default.csv", _mode_block(1, filename="default.csv"),
               prefs=("enable_DS3_emulation,6,,,",))
    r = _post(client, src)
    assert r.status_code == 201, r.text                     # stored, so it can be fixed here
    pid = r.json()["profile"]["id"]
    v = client.get(f"/profiles/{pid}/validate").json()
    hidden = _drive_findings(v["findings"])
    assert v["errors"] >= 1 and hidden and hidden[0]["severity"] == "error"
    assert "every boot" in hidden[0]["message"]
    r = client.get(f"/profiles/{pid}/export.csv")
    assert r.status_code == 409
    assert _drive_findings(r.json()["detail"]["validation"]["findings"])
    # the same file under an ordinary name is only a warning, and exports
    src = _csv(tmp_path, "m.csv", _mode_block(1), prefs=("enable_DS3_emulation,6,,,",))
    pid = _post(client, src).json()["profile"]["id"]
    assert client.get(f"/profiles/{pid}/validate").json()["errors"] == 0
    assert client.get(f"/profiles/{pid}/export.csv").status_code == 200


def test_import_refusal_carries_the_findings_and_leaves_no_half_profile(client, tmp_path):
    """Whatever refuses the import, the response carries the findings and nothing is stored."""
    rows = ("increment_mode,normal,right_sip,", "fire_button,normal,lip,")     # unknown output
    r = _post(client, _csv(tmp_path, "m.csv", _mode_block(1, rows=rows)))
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "fire_button" in detail["message"]
    assert any("fire_button" in f["message"] for f in detail["validation"]["findings"])
    assert client.get("/profiles").json() == []
    # and the session is usable afterwards
    assert upload(client, FIXTURES / "cod.csv")["profile"]["id"]


def test_a_blank_c1_label_survives_get_put_export(client, tmp_path):
    """`Profile Name,,,` is legal on the device. The import keeps the label empty
    and the UI shows a fallback; a PUT of what GET returned must not turn the
    empty cell into `Mode 1`, or the export would differ from the file."""
    src = _csv(tmp_path, "m.csv", _mode_block(1, label=""))
    r = _post(client, src)
    assert r.status_code == 201, r.text
    pid = r.json()["profile"]["id"]
    doc = client.get(f"/profiles/{pid}").json()
    assert doc["modes"][0]["label"] == ""
    assert client.put(f"/profiles/{pid}", json=doc).status_code == 200
    assert client.get(f"/profiles/{pid}").json()["modes"][0]["label"] == ""
    out = client.get(f"/profiles/{pid}/export.csv")
    assert out.status_code == 200, out.text
    assert out.content == src.read_bytes()


def test_import_findings_come_errors_first_in_mode_and_row_order_and_only_once(client, tmp_path):
    """An info from the parser before an error from the validator used to come back
    in file order, and a rule both of them check came back twice. Within a severity
    the order is (mode, row): the parser's problems used to sit before the
    validator's, so a parser info on row 7 came before a validator info on row 5.
    Findings with no mode (file level) or no row (mode level) come last."""
    rows = ("increment_mode,normal,right_sip,", "x,,lip,",          # row 5, empty cell: validator info
            "x,repeat five 2000,lip,",                              # row 6: error
            "left_joy_up,normal,up,",
            "square, normal,lip,")                                  # row 8: parser info (whitespace)
    body = (_mode_block(1, rows=rows, filename="M.csv")             # A2 mixed case: file-level info
            + _mode_block(2, label="M2", rows=("x,,lip,", "decrement_mode,normal,right_puff,")))
    r = _post(client, _csv(tmp_path, "M.csv", body))
    assert r.status_code == 201, r.text
    fs = r.json()["findings"]["findings"]
    rank = {"error": 0, "warning": 1, "info": 2}
    ranks = [rank[f["severity"]] for f in fs]
    assert ranks == sorted(ranks) and ranks[0] == 0 and 2 in ranks
    keys = [(f["severity"], f["mode"], f["row"], " ".join(f["message"].split()).lower()) for f in fs]
    assert len(keys) == len(set(keys))
    infos = [(f["mode"], f["row"]) for f in fs if f["severity"] == "info"]
    assert (1, 5) in infos and (1, 8) in infos and (2, 4) in infos and (None, 2) in infos
    assert infos.index((1, 5)) < infos.index((1, 8)) < infos.index((2, 4)) < infos.index((None, 2))
    # and every severity block is in (mode, row) order, None last
    for sev in ("error", "warning", "info"):
        block = [(f["mode"], f["row"]) for f in fs if f["severity"] == sev]
        assert block == sorted(block, key=lambda mr: (mr[0] is None, mr[0] or 0, mr[1] is None, mr[1] or 0)), sev
