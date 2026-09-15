"""Global preferences: the device's own prefs.csv, which sits underneath every
profile (prefs.csv < profile Preferences < per-mode override)."""
from qsprofile import catalog as C
from qsprofile import read_prefs_csv


def test_starts_empty_and_stores_a_set(client):
    assert client.get("/prefs").json()["preferences"] == {}
    r = client.put("/prefs", json={"preferences": {"volume": "40", "brightness": "7"}})
    assert r.status_code == 200, r.text
    assert r.json()["preferences"] == {"volume": "40", "brightness": "7"}
    assert client.get("/prefs").json()["preferences"] == {"volume": "40", "brightness": "7"}


def test_put_replaces_rather_than_merges(client):
    client.put("/prefs", json={"preferences": {"volume": "40", "brightness": "7"}})
    client.put("/prefs", json={"preferences": {"volume": "10"}})
    assert client.get("/prefs").json()["preferences"] == {"volume": "10"}


def test_a_value_outside_the_firmware_range_is_refused(client):
    meta = C.PREFERENCES["volume"]
    too_high = str((meta["maximum"] or 100) + 1)
    r = client.put("/prefs", json={"preferences": {"volume": too_high}})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "outside what the QuadStick accepts" in detail["message"]
    assert any("the highest the QuadStick accepts" in f["message"]
               for f in detail["validation"]["findings"])
    # and nothing was stored
    assert client.get("/prefs").json()["preferences"] == {}


def test_a_non_numeric_value_is_refused_with_the_setting_named(client):
    r = client.put("/prefs", json={"preferences": {"volume": "loud"}})
    assert r.status_code == 422
    msgs = [f["message"] for f in r.json()["detail"]["validation"]["findings"]]
    assert any("Speaker volume" in m and "whole number" in m for m in msgs)


def test_a_choice_outside_its_options_is_refused(client):
    key = "mouse_response_curve"
    assert C.PREFERENCES[key]["editor"] == "choice"
    r = client.put("/prefs", json={"preferences": {key: "99"}})
    assert r.status_code == 422
    assert any("must be one of" in f["message"]
               for f in r.json()["detail"]["validation"]["findings"])


def test_a_toggle_only_takes_0_or_1(client):
    key = next(k for k, v in C.PREFERENCES.items() if v["editor"] == "toggle")
    assert client.put("/prefs", json={"preferences": {key: "1"}}).status_code == 200
    assert client.put("/prefs", json={"preferences": {key: "2"}}).status_code == 422


def test_an_unknown_key_is_kept_and_reported_once_at_import(client, tmp_path):
    """The device may know settings this catalog does not, so they are stored and
    exported as they are. The report comes from read_prefs_csv alone (one source),
    so an import shows it exactly once and a PUT does not repeat it. The router
    tells that note apart by its `code`, never by its wording."""
    r = client.put("/prefs", json={"preferences": {"some_future_setting": "1"}})
    assert r.status_code == 200
    assert r.json()["preferences"] == {"some_future_setting": "1"}
    assert not [f for f in r.json()["validation"]["findings"] if f["code"] == "unknown_preference"]
    assert not [f for f in client.get("/prefs").json()["validation"]["findings"] if f["code"] == "unknown_preference"]
    src = tmp_path / "prefs.csv"
    src.write_bytes(b"Preferences,\r\n,,,,\r\nPreference,Value,Units,Description,\r\n"
                    b"some_future_setting,1,,,\r\nvolume,20,,,\r\n\r\n")
    with open(src, "rb") as f:
        r = client.post("/prefs/import", files={"file": ("prefs.csv", f)})
    assert r.status_code == 200, r.text
    reports = [f for f in r.json()["validation"]["findings"] if "some_future_setting" in f["message"]]
    assert len(reports) == 1 and "not a preference this app knows" in reports[0]["message"]
    assert reports[0]["code"] == "unknown_preference" and reports[0]["severity"] == "info"
    assert [f for f in r.json()["validation"]["findings"] if f["code"] == "unknown_preference"] == reports
    assert r.json()["preferences"] == {"some_future_setting": "1", "volume": "20"}


def test_a_device_wide_drive_hiding_mode_is_an_error(client):
    """prefs.csv applies at every boot, so there is no profile to switch away from:
    a drive-hiding mode here is refused outright, not warned about."""
    r = client.put("/prefs", json={"preferences": {"enable_DS3_emulation": "6"}})
    assert r.status_code == 422, r.text
    errors = [f for f in r.json()["detail"]["validation"]["findings"] if f["severity"] == "error"]
    assert errors and "hides the flash drive" in errors[0]["message"]
    # and it says why device-wide is worse than per-profile
    assert "every profile" in errors[0]["message"] and "firmware 2373" in errors[0]["message"]
    assert client.get("/prefs").json()["preferences"] == {}
    # mode 4, the one actually in use, is fine
    r = client.put("/prefs", json={"preferences": {"enable_DS3_emulation": "4"}})
    assert r.status_code == 200
    assert not [f for f in r.json()["validation"]["findings"] if f["severity"] in ("warning", "error")]


def test_the_drive_hiding_check_follows_the_firmware_given(client):
    """Which modes hide the drive is a firmware fact (catalog.hidden_drive_modes), never
    hard-wired: mode 6 hides it on 2373 but not on 1476."""
    hidden_2373, hidden_1476 = C.HIDDEN_DRIVE_MODES[2373], C.HIDDEN_DRIVE_MODES[1476]
    assert hidden_1476 <= hidden_2373, "2373 is the union until modes 1 and 3 are verified"
    only_2373 = min(hidden_2373 - hidden_1476)
    body = {"preferences": {"enable_DS3_emulation": str(only_2373)}}
    assert client.put("/prefs", json=body, params={"firmware": 1476}).status_code == 200
    r = client.put("/prefs", json=body, params={"firmware": 2373})
    assert r.status_code == 422
    assert any("firmware 2373" in f["message"] for f in r.json()["detail"]["validation"]["findings"])
    # the stored value is judged against the firmware asked about, on read and on export
    assert client.get("/prefs", params={"firmware": 1476}).json()["validation"]["errors"] == 0
    assert client.get("/prefs", params={"firmware": 2373}).json()["validation"]["errors"] == 1
    assert client.get("/prefs/export.csv", params={"firmware": 1476}).status_code == 200
    assert client.get("/prefs/export.csv", params={"firmware": 2373}).status_code == 409
    # the default is the owner's firmware; an unknown one is refused
    assert client.get("/prefs").json()["validation"]["errors"] == 1
    r = client.get("/prefs", params={"firmware": 9999})
    assert r.status_code == 422 and "Unknown firmware 9999" in r.text and "2373" in r.text
    assert client.put("/prefs", json=body, params={"firmware": 9999}).status_code == 422
    assert client.get("/prefs/export.csv", params={"firmware": 9999}).status_code == 422


def test_export_is_the_prefs_csv_the_device_reads(client, tmp_path):
    client.put("/prefs", json={"preferences": {"volume": "40", "sip_puff_threshold": "55"}})
    r = client.get("/prefs/export.csv")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="prefs.csv"'
    text = r.content.decode()
    # the QMP header the firmware's prefs loader requires (C1), then the same
    # Preferences block a profile carries: no mode blocks, CRLF, trailing commas
    assert text.startswith("QuadStick Configuration,Version 1.1\r\nPreferences,,,,\r\nprefs.csv,,,,\r\n")
    assert "Profile Name" not in text
    assert "Preference,Value,Units,Description,\r\n" in text
    assert "volume,40,,,\r\n" in text
    # and it reads back as what we put in
    out = tmp_path / "prefs.csv"
    out.write_bytes(r.content)
    back, _ = read_prefs_csv(str(out))
    assert back == {"volume": "40", "sip_puff_threshold": "55"}


def test_export_refuses_when_there_is_nothing_to_write(client):
    assert client.get("/prefs/export.csv").status_code == 409


def test_import_reads_a_prefs_csv_off_the_flash_drive(client, tmp_path):
    src = tmp_path / "prefs.csv"
    src.write_bytes(b"Preferences,\r\n,,,,\r\nPreference,Value,Units,Description,\r\n"
                    b"volume,25,,,\r\nbrightness,9,,,\r\n\r\n")
    with open(src, "rb") as f:
        r = client.post("/prefs/import", files={"file": ("prefs.csv", f)})
    assert r.status_code == 200, r.text
    assert r.json()["preferences"] == {"volume": "25", "brightness": "9"}
    assert client.get("/prefs").json()["preferences"] == {"volume": "25", "brightness": "9"}


def test_importing_a_profile_by_mistake_is_refused_and_leaves_the_globals_untouched(client, tmp_path):
    """A profile .csv also has a Preferences block, so the mistake is easy to make;
    it used to replace the whole device-wide set with the profile's block."""
    from conftest import FIXTURES
    client.put("/prefs", json={"preferences": {"volume": "40", "brightness": "7"}})
    with open(FIXTURES / "cod.csv", "rb") as f:
        r = client.post("/prefs/import", files={"file": ("cod.csv", f)})
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "is a profile" in detail["message"] and "unchanged" in detail["message"]
    assert any("profile .csv rather than prefs.csv" in f["message"] and f["code"] == "not_a_prefs_file"
               for f in detail["validation"]["findings"])
    assert client.get("/prefs").json()["preferences"] == {"volume": "40", "brightness": "7"}


def test_importing_a_file_with_no_settings_is_refused_and_leaves_the_globals_untouched(client, tmp_path):
    client.put("/prefs", json={"preferences": {"volume": "40"}})
    for name, content in (("prefs.csv", b""), ("prefs.csv", b"Preferences,\r\n,,,,\r\n"),
                          ("notes.csv", b"just,some,text\r\n")):
        src = tmp_path / name
        src.write_bytes(content)
        with open(src, "rb") as f:
            r = client.post("/prefs/import", files={"file": (name, f)})
        assert r.status_code == 422, (name, r.text)
        assert "no settings were found" in r.json()["detail"]["message"]
    assert client.get("/prefs").json()["preferences"] == {"volume": "40"}


def test_import_rejects_a_non_csv(client, tmp_path):
    p = tmp_path / "prefs.txt"
    p.write_text("nope")
    with open(p, "rb") as f:
        assert client.post("/prefs/import", files={"file": ("prefs.txt", f)}).status_code == 415


def test_global_prefs_do_not_leak_into_a_profile(client):
    """They are separate scopes: a profile's own Preferences sheet is its own set."""
    client.put("/prefs", json={"preferences": {"volume": "40"}})
    # a profile needs at least one mode with a way out, or export is refused
    p = client.post("/profiles", json={
        "name": "T", "csv_filename": "t.csv",
        "modes": [{"name": "M", "mappings": [
            {"output": "increment_mode", "inputs": ["right_sip"]},
            {"output": "left_joy_up", "inputs": ["up"]},
        ]}],
        "preferences": {"brightness": "3"},
    }).json()
    assert p["preferences"] == {"brightness": "3"}
    assert client.get("/prefs").json()["preferences"] == {"volume": "40"}
    # and the profile's export carries only its own
    csv = client.get(f"/profiles/{p['id']}/export.csv").content.decode()
    assert "brightness,3" in csv
    assert "volume,40" not in csv
