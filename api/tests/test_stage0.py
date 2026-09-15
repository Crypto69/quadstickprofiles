"""Stage 0 on the API side: firmware, legacy input names, per-mode preference
override rows, the richer validate response, stateless validate, duplicate, /api."""
from qsprofile import catalog as C
from conftest import FIXTURES, upload


# ---------------------------------------------------------------- 0.9 mounting
def test_everything_is_mounted_under_api(root_client):
    assert root_client.get("/api/health").json() == {"status": "ok"}
    assert root_client.get("/health").json() == {"status": "ok"}      # kept for the health check
    assert root_client.get("/api/catalog").status_code == 200
    assert root_client.get("/catalog").status_code == 404             # no longer at the root
    assert root_client.get("/profiles").status_code == 404
    assert root_client.get("/api/openapi.json").status_code == 200


def test_version_reports_the_readable_deploy_number(root_client, monkeypatch):
    monkeypatch.setenv("QS_APP_VERSION", "1.7")
    v = root_client.get("/api/version").json()
    assert v["app_version"] == "1.7"
    assert set(v) == {"version", "app_version", "commit", "built"}


# ---------------------------------------------------------------- 0.3 legacy inputs
def test_legacy_input_names_are_in_the_catalog_so_the_fk_holds(client):
    inputs = {i["name"]: i for i in client.get("/catalog").json()["inputs"]}
    for name in C.LEGACY_INPUTS:
        assert name in inputs, f"{name} missing from input_catalog; a profile using it would fail the FK"
        assert inputs[name]["kind"] == "legacy"
    assert client.get("/catalog").json()["legacy_inputs"] == C.LEGACY_INPUTS


def _every_accepted_input_name():
    """The full vocabulary classify_input() accepts, built independently of
    catalog_seed so the seed cannot define away its own gap (C1)."""
    cand = {"lip", "lip_soft", "center", "any_direction"}
    cand |= {f"mp_{t}_{a}{s}" for t in C.TUBES for a in ("sip", "puff") for s in ("", "_soft")}
    cand |= {f"right_{a}{s}" for a in ("sip", "puff") for s in ("", "_soft")}
    cand |= {f"{d}{r}" for d in C.JOY_DIRS + C.JOY_ZONES for r in ("", "_inner")}
    cand |= {f"digital_in_{n}" for n in range(1, 9)}
    cand |= {f"usb_{u}_{d}{r}" for u in (1, 2)
             for d in C.JOY_DIRS + C.JOY_ZONES + [f"button_{n}" for n in range(1, 17)]
             for r in ("", "_inner")}
    cand |= set(C.SPECIAL_INPUTS) | set(C.LEGACY_INPUTS)
    return {n for n in cand if C.classify_input(n)}


def test_every_input_the_validator_accepts_is_seeded_so_the_fk_holds(client):
    """The API pre-check is classify_input(); if the seed knows fewer names than it
    does, saving one of the others fails the mapping_inputs FK with a 500."""
    inputs = {i["name"] for i in client.get("/catalog").json()["inputs"]}
    missing = sorted(_every_accepted_input_name() - inputs)
    assert not missing, f"accepted by classify_input() but absent from input_catalog: {missing}"
    # and the names C1 found missing are there under the kind classify_input() gives them
    by_name = {i["name"]: i for i in client.get("/catalog").json()["inputs"]}
    for n in ("constant", "none", "any_direction", "mp_right_mode_sip", "mp_right_mode_sip_soft",
              "mp_right_mode_puff", "mp_right_mode_puff_soft", "usb_1_button_16",
              "usb_1_button_16_inner", "usb_2_button_16", "usb_2_button_16_inner"):
        assert n in by_name, n
        assert by_name[n]["kind"] == C.classify_input(n)["kind"], n


def test_the_inputs_c1_found_missing_can_actually_be_saved(client):
    body = {"name": "C1", "csv_filename": "c1.csv", "modes": [{"name": "M", "mappings": [
        {"output": "x", "inputs": ["constant"]},
        {"output": "circle", "inputs": ["none"]},
        {"output": "square", "inputs": ["mp_right_mode_sip"]},
        {"output": "triangle", "inputs": ["mp_right_mode_puff_soft"]},
        {"output": "left_1", "inputs": ["usb_1_button_16"]},
        {"output": "right_1", "inputs": ["usb_2_button_16_inner"]},
        {"output": "left_2", "inputs": ["any_direction"]},
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]}
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    v = client.get(f"/profiles/{r.json()['id']}/validate").json()
    assert v["errors"] == 0, v["findings"]
    assert client.get(f"/profiles/{r.json()['id']}/export.csv").status_code == 200


def test_a_profile_using_a_legacy_input_saves_and_is_warned_about(client):
    body = {"name": "Legacy", "csv_filename": "legacy.csv",
            "modes": [{"name": "M", "mappings": [
                {"output": "x", "inputs": ["push"]},
                {"output": "increment_mode", "inputs": ["right_sip"]},
            ]}]}
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    v = client.get(f"/profiles/{r.json()['id']}/validate").json()
    assert any("older input name" in f["message"] for f in v["findings"])


# ---------------------------------------------------------------- 0.2 firmware
def test_firmware_decides_which_emulation_modes_hide_the_drive(client):
    """The emulation mode is the file's own enable_DS3_emulation row; which values
    hide the drive is a firmware fact (catalog.hidden_drive_modes), never hard-coded."""
    modes = [{"name": "M", "mappings": [{"output": "increment_mode", "inputs": ["right_sip"]}]}]
    body = {"name": "FW", "csv_filename": "fw.csv", "firmware": 2373, "modes": modes,
            "preferences": {"enable_DS3_emulation": "6"}}
    p = client.post("/profiles", json=body).json()
    assert p["firmware"] == 2373 and p["preferences"] == {"enable_DS3_emulation": "6"}

    def drive_findings(fw, mode):
        body["firmware"], body["preferences"]["enable_DS3_emulation"] = fw, str(mode)
        assert client.put(f"/profiles/{p['id']}", json=body).status_code == 200
        return [f for f in client.get(f"/profiles/{p['id']}/validate").json()["findings"]
                if "hides the flash drive" in f["message"]]

    hidden = drive_findings(2373, 6)
    assert hidden and "firmware 2373" in hidden[0]["message"] and hidden[0]["severity"] == "warning"
    # 2373 is the union {1,3,5,6,7} until modes 1 and 3 are verified on the device; 1476 is {3,5,7}
    for fw in (2373, 1476):
        assert any(f"firmware {fw}" in f["message"] for f in drive_findings(fw, 3)), fw
    assert drive_findings(1476, 6) == []            # 6 hides it on 2373 only
    for fw in (2373, 1476):
        assert drive_findings(fw, 4) == [], fw       # the owner's mode is safe on both
    assert {int(m) for m in C.HIDDEN_DRIVE_MODES[2373]} == {1, 3, 5, 6, 7}


def test_unknown_firmware_is_refused(client):
    r = client.post("/profiles", json={"name": "T", "csv_filename": "t.csv", "firmware": 9999})
    assert r.status_code == 422
    assert client.patch("/profiles/1", json={"firmware": 9999}).status_code in (404, 422)


def test_import_defaults_to_owner_firmware(client):
    got = upload(client, FIXTURES / "cod.csv")
    assert got["profile"]["firmware"] == C.DEFAULT_FIRMWARE == 2373


# ---------------------------------------------------------------- 0.7 preference override rows
def test_imported_preference_override_row_is_kept_not_dropped(client):
    """Before migration 0002 the mappings table had nowhere to put this row."""
    got = upload(client, FIXTURES / "synthetic_pref_override.csv")
    mode2 = got["profile"]["modes"][1]["mappings"]
    overrides = [m for m in mode2 if m["kind"] == "preference"]
    assert [(m["output"], m["value"]) for m in overrides] == \
           [("sip_puff_threshold", "55"), ("mouse_speed", "120")]
    assert all(m["inputs"] == [] for m in overrides)
    assert any("for this mode only" in f["message"] for f in got["findings"]["findings"])


def test_preference_override_survives_export_byte_for_byte(client):
    got = upload(client, FIXTURES / "synthetic_pref_override.csv")
    out = client.get(f"/profiles/{got['profile']['id']}/export.csv").content
    assert out == (FIXTURES / "synthetic_pref_override.csv").read_bytes()


def test_preference_override_can_be_written_through_the_api(client):
    body = {"name": "Ov", "csv_filename": "ov.csv", "modes": [{"name": "M", "mappings": [
        {"kind": "preference", "output": "mouse_speed", "value": "150"},
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]}
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    m = r.json()["modes"][0]["mappings"][0]
    assert m["kind"] == "preference" and m["output"] == "mouse_speed" and m["value"] == "150"


def test_a_bad_preference_override_row_is_refused(client):
    base = {"name": "Ov", "csv_filename": "ov.csv"}
    for mapping in [
        {"kind": "preference", "output": "not_a_preference", "value": "1"},     # unknown key
        {"kind": "preference", "output": "mouse_speed", "value": "1", "inputs": ["lip"]},   # has inputs
        {"output": "x", "value": "1", "inputs": ["lip"]},                       # value on a mapping row
    ]:
        r = client.post("/profiles", json={**base, "modes": [{"name": "M", "mappings": [mapping]}]})
        assert r.status_code == 422, mapping


def test_sequence_rows_are_flagged_for_the_editor(client):
    body = {"name": "Seq", "csv_filename": "seq.csv", "modes": [{"name": "M", "mappings": [
        {"output": "x", "inputs": ["mp_left_sip", "mp_right_sip"]},
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]}
    p = client.post("/profiles", json=body).json()
    rows = p["modes"][0]["mappings"]
    assert rows[0]["is_sequence"] is True and rows[1]["is_sequence"] is False


# ---------------------------------------------------------------- 0.8 validate response
def test_validate_reports_budget_consequence_and_unused_inputs(client):
    got = upload(client, FIXTURES / "cod.csv")
    v = client.get(f"/profiles/{got['profile']['id']}/validate").json()
    b = v["budget"]
    assert b["modes_max"] == C.MAX_MODES and b["rows_max"] == C.MAX_ROWS_PER_MODE
    assert b["firmware"] == C.DEFAULT_FIRMWARE
    assert b["modes_used"] == len(got["profile"]["modes"]) == len(b["modes"])
    m0 = b["modes"][0]
    assert m0["rows_used"] == len(got["profile"]["modes"][0]["mappings"])
    assert m0["rows_free"] == C.MAX_ROWS_PER_MODE - m0["rows_used"]
    assert m0["rows_active"] <= m0["rows_used"]
    assert b["preference_rows_max"] == C.MAX_PREFERENCE_ROWS[C.DEFAULT_FIRMWARE]
    # consequence is stated per severity actually present, in device terms, and only those
    present = {f["severity"] for f in v["findings"]}
    assert present and set(v["consequence"]) == present
    assert "error" not in v["consequence"], "cod.csv has no errors, so none to state"
    for sev, text in v["consequence"].items():
        assert "QuadStick" in text or "Nothing to fix" in text, (sev, text)
    # unused_inputs = free in every mode, so it is a subset of each mode's free list
    for m in b["modes"]:
        assert set(v["unused_inputs"]) <= set(m["unused_inputs"])


def test_catalog_exposes_the_firmware_knowledge_the_editor_needs(client):
    cat = client.get("/catalog").json()
    assert len(cat["preferences"]) == len(C.PREFERENCES) == 61
    assert cat["preferences"]["mouse_speed"]["label"] == C.PREFERENCES["mouse_speed"]["label"]
    assert set(cat["mode_overridable"]) == set(C.MODE_OVERRIDABLE)
    assert cat["preference_categories"] == list(C.PREFERENCE_CATEGORIES)
    assert cat["emulation_modes"]["4"] == C.EMULATION_MODES[4]
    assert cat["hidden_drive_modes"]["2373"] == [1, 3, 5, 6, 7]      # union until 1 and 3 are verified
    assert cat["hidden_drive_modes"]["1476"] == [3, 5, 7]
    assert cat["firmware_versions"] == list(C.FIRMWARE_VERSIONS)
    assert cat["default_firmware"] == 2373
    # the off-by-one limits: next_word() gives up at 64 chars and f_gets keeps len-1
    assert cat["limits"] == {"max_modes": 16, "max_rows_per_mode": 128,
                             "max_keyword_chars": 63, "max_line_bytes": 1023,
                             "max_function_param": 16383}


# ---------------------------------------------------------------- 0.8 stateless validate
def test_stateless_validate_writes_nothing(client):
    before = len(client.get("/profiles").json())
    body = {"name": "Draft", "csv_filename": "draft.csv", "firmware": 2373,
            "preferences": {"enable_DS3_emulation": "6"},
            "modes": [{"name": "M", "mappings": [
                {"output": "x", "inputs": ["mp_center_sip"]},
                {"output": "x", "inputs": ["mp_center_sip"]},          # duplicate -> warning
            ]}]}
    v = client.post("/profiles/validate", json=body).json()
    assert any("mapped twice" in f["message"] for f in v["findings"])
    assert any("no increment_mode" in f["message"] for f in v["findings"])
    assert any("hides the flash drive" in f["message"] for f in v["findings"])
    assert v["budget"]["modes_used"] == 1 and v["budget"]["modes"][0]["rows_used"] == 2
    assert v["consequence"]["warning"]
    assert len(client.get("/profiles").json()) == before        # nothing persisted


def test_repeat_zero_is_a_finding_not_a_schema_rejection(client):
    """Parameter *values* are the firmware's business: `repeat 0` divides by zero
    there and `2.5` is read with atoi, so both come back as row-anchored errors the
    editor can show, and export is blocked by them. An import stores `repeat 2.5 2000`
    as the file says, so a save or a live check of that row is not a 422 either."""
    modes = [{"name": "M", "mappings": [
        {"output": "x", "function": "repeat", "params": [0, 2000], "inputs": ["lip"]},
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]
    body = {"name": "R0", "csv_filename": "r0.csv", "modes": modes}
    r = client.post("/profiles/validate", json=body)
    assert r.status_code == 200, r.text
    bad = [f for f in r.json()["findings"] if "divides by zero" in f["message"]]
    assert bad and bad[0]["severity"] == "error" and bad[0]["mode"] == 1 and bad[0]["row"] == 4
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    assert client.get(f"/profiles/{r.json()['id']}/export.csv").status_code == 409
    modes[0]["mappings"][0]["params"] = [2.5, 2000]
    r = client.post("/profiles/validate", json=body)
    assert r.status_code == 200, r.text
    assert any("whole numbers" in f["message"] and f["severity"] == "error" and f["row"] == 4
               for f in r.json()["findings"])
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    assert client.get(f"/profiles/{r.json()['id']}/export.csv").status_code == 409


def test_stateless_validate_handles_preference_rows_and_errors(client):
    body = {"name": "Draft", "csv_filename": "draft.csv", "modes": [{"name": "M", "mappings": [
        {"kind": "preference", "output": "sip_puff_threshold", "value": "55"},
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]}
    v = client.post("/profiles/validate", json=body).json()
    assert v["errors"] == 0
    assert any("for this mode only" in f["message"] for f in v["findings"])


def test_stateless_validate_reports_a_bad_filename_and_blank_name_as_findings(client):
    """Live checks: the editor needs the rule-1 finding to show against the field, not a
    422 it can only render as "request failed". Saving still refuses these (ProfileMeta)."""
    for bad in ("bad name.csv", "../x.csv", "a" * 28 + ".csv", ""):
        r = client.post("/profiles/validate", json={"name": "D", "csv_filename": bad,
                                                    "modes": [{"name": "M", "mappings": [
                                                        {"output": "increment_mode", "inputs": ["right_sip"]}]}]})
        assert r.status_code == 200, (bad, r.text)
        assert any(f["severity"] == "error" and f["row"] == 2 and "A2" in f["message"]
                   for f in r.json()["findings"]), (bad, r.json()["findings"])
    r = client.post("/profiles/validate", json={"name": "", "csv_filename": "ok.csv"})
    assert r.status_code == 200, r.text
    # a 17th mode is the rule-6 finding, not a schema rejection
    modes = [{"name": f"M{n}", "mappings": [{"output": "increment_mode", "inputs": ["right_sip"]}]}
             for n in range(1, 18)]
    r = client.post("/profiles/validate", json={"name": "D", "csv_filename": "ok.csv", "modes": modes})
    assert r.status_code == 200, r.text
    assert any("at most 16" in f["message"] for f in r.json()["findings"])
    assert r.json()["budget"]["modes_used"] == 17
    # the same document cannot be saved, and the editor must not lose the row keywords rule
    assert client.post("/profiles", json={"name": "D", "csv_filename": "bad name.csv"}).status_code == 422
    assert client.post("/profiles/validate", json={"name": "D", "csv_filename": "ok.csv", "modes": [
        {"name": "M", "mappings": [{"output": "fire", "inputs": ["lip"]}]}]}).status_code == 422
    assert client.post("/profiles/validate", json={"name": "D", "csv_filename": "ok.csv",
                                                   "firmware": 9999}).status_code == 422


# ---------------------------------------------------------------- 0.8 duplicate
def test_duplicate_copies_everything_and_takes_a_new_filename(client):
    got = upload(client, FIXTURES / "synthetic_pref_override.csv", game="Call of Duty")
    src = got["profile"]
    client.patch(f"/profiles/{src['id']}", json={"input_names": {"lip": "Chin switch"}})
    r = client.post(f"/profiles/{src['id']}/duplicate")
    assert r.status_code == 201, r.text
    copy = r.json()
    assert copy["id"] != src["id"]
    assert copy["csv_filename"] == "synthpref_copy.csv"            # the device picks files by filename
    # W: the default name is the filename's stem, so name and file agree on the stick.
    # It used to be "<name> (copy)", which paired a name with a file that looked nothing
    # like it and made a stick full of copies unreadable.
    assert copy["name"] == "synthpref_copy"
    assert C.csv_filename_for_name(copy["name"]) == copy["csv_filename"]
    assert copy["firmware"] == src["firmware"] and copy["preferences"] == src["preferences"]
    assert copy["input_names"] == {"lip": "Chin switch"}
    assert len(copy["modes"]) == len(src["modes"])
    # the per-mode override rows came along
    overrides = [m for m in copy["modes"][1]["mappings"] if m["kind"] == "preference"]
    assert [(m["output"], m["value"]) for m in overrides] == \
           [("sip_puff_threshold", "55"), ("mouse_speed", "120")]
    # and the copy exports the same rows under its own filename
    csv = client.get(f"/profiles/{copy['id']}/export.csv").content.decode()
    assert "synthpref_copy.csv,,Normal," in csv
    assert "sip_puff_threshold,,55," in csv


def test_duplicate_accepts_a_name_and_filename_and_rejects_a_bad_one(client):
    got = upload(client, FIXTURES / "cod.csv")
    sid = got["profile"]["id"]
    r = client.post(f"/profiles/{sid}/duplicate", params={"name": "COD tweak", "csv_filename": "codtweak.csv"})
    assert r.status_code == 201
    assert r.json()["name"] == "COD tweak" and r.json()["csv_filename"] == "codtweak.csv"
    assert client.post(f"/profiles/{sid}/duplicate", params={"csv_filename": "bad name.csv"}).status_code == 422
    assert client.post("/profiles/999999/duplicate").status_code == 404


def test_error_consequence_is_stated_and_export_is_blocked(client):
    """An over-long mode is a firmware limit error: the device would not read the
    profile, so the response says so and export is refused."""
    rows = [{"output": "x", "inputs": ["mp_center_sip"]} for _ in range(129)]
    body = {"name": "Too big", "csv_filename": "toobig.csv",
            "modes": [{"name": "M", "mappings": rows}]}
    v = client.post("/profiles/validate", json=body).json()
    assert v["errors"] >= 1
    assert any("at most 128" in f["message"] for f in v["findings"])
    assert "will not read this profile" in v["consequence"]["error"]
    p = client.post("/profiles", json=body).json()
    r = client.get(f"/profiles/{p['id']}/export.csv")
    assert r.status_code == 409
    assert r.json()["detail"]["validation"]["errors"] >= 1


def test_mode_channel_both_and_none_are_accepted_on_write(client):
    """C3 may say both or none as well as usb / bluetooth; the schema used to refuse the
    first two while core and the device accept them."""
    for ch in ("usb", "bluetooth", "both", "none"):
        body = {"name": "Ch", "csv_filename": "ch.csv",
                "modes": [{"name": "M", "channel": ch, "mappings": [
                    {"output": "increment_mode", "inputs": ["right_sip"]}]}]}
        r = client.post("/profiles", json=body)
        assert r.status_code == 201, (ch, r.text)
        assert r.json()["modes"][0]["channel"] == ch
        assert f"Output or Function,Function,{ch}," in client.get(
            f"/profiles/{r.json()['id']}/export.csv").content.decode()
    # an off-catalog channel is a finding, not a bad request (W4): an import stores C3
    # as the file held it, so what GET returns must PUT back or the profile freezes.
    r = client.post("/profiles", json={"name": "Ch", "csv_filename": "ch.csv",
                                       "modes": [{"name": "M", "channel": "wifi"}]})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["modes"][0]["channel"] == "wifi"
    findings = client.get(f"/profiles/{pid}/validate").json()["findings"]
    assert any(f["severity"] == "error" and f["mode"] == 1 and f["row"] == 3 for f in findings), findings
    assert client.get(f"/profiles/{pid}/export.csv").status_code == 409
    # the text rule still applies: a comma in C3 would shift the cells of the file
    r = client.post("/profiles", json={"name": "Ch", "csv_filename": "ch.csv",
                                       "modes": [{"name": "M", "channel": "us,b"}]})
    assert r.status_code == 422, r.text
