"""Decision D4: nothing that reaches write_csv may carry a comma, a line break or
non-ASCII, because write_csv never quotes and the firmware never unquotes. The save
paths refuse such text with a 422; the live check reports it as core's finding, so
the editor can show it against the field."""
from conftest import FIXTURES, upload

MODES = [{"name": "M", "mappings": [{"output": "increment_mode", "inputs": ["right_sip"]},
                                    {"output": "left_joy_up", "inputs": ["up"]}]}]


def _doc(**over):
    return {"name": "T", "csv_filename": "t.csv", "modes": [dict(m) for m in MODES], **over}


def _errors(client, doc):
    r = client.post("/profiles/validate", json=doc)
    assert r.status_code == 200, r.text
    return [f["message"] for f in r.json()["findings"] if f["severity"] == "error"]


def test_a_comma_in_a_mode_name_is_refused_on_save_and_reported_by_the_live_check(client):
    p = client.post("/profiles", json=_doc()).json()
    doc = _doc(modes=[{**MODES[0], "name": "Left, right"}])
    assert client.put(f"/profiles/{p['id']}", json=doc).status_code == 422
    assert client.post("/profiles", json=doc).status_code == 422
    assert any("comma" in m for m in _errors(client, doc))
    doc = _doc(modes=[{**MODES[0], "label": "Vis\u00e9e"}])              # non-ASCII C1
    assert client.put(f"/profiles/{p['id']}", json=doc).status_code == 422
    assert any("ASCII" in m for m in _errors(client, doc))
    assert client.get(f"/profiles/{p['id']}").json()["modes"][0]["name"] == "M"


def test_a_preference_value_with_a_comma_is_refused(client):
    for prefs in ({"bluetooth_remote_address": "aa,bb"}, {"volume": "4\r\n0"}, {"some,key": "1"}):
        doc = _doc(preferences=prefs)
        assert client.post("/profiles", json=doc).status_code == 422, prefs
        assert _errors(client, doc), prefs
    p = client.post("/profiles", json=_doc()).json()
    assert client.put(f"/profiles/{p['id']}", json=_doc(preferences={"bluetooth_remote_address": "aa,bb"})).status_code == 422
    # the same rule for a per-mode override row's value
    doc = _doc(modes=[{"name": "M", "mappings": [
        {"kind": "preference", "output": "mouse_speed", "value": "1,2"}] + MODES[0]["mappings"]}])
    assert client.post("/profiles", json=doc).status_code == 422
    assert any("comma" in m for m in _errors(client, doc))


def test_line_1_follows_the_firmware_rule(client):
    """The firmware reads only the first word of line 1, so a comma in the title cannot
    shift a block: core warns that the name reads back cut short, and the save goes
    through. A line break or non-ASCII there is still refused."""
    r = client.post("/profiles", json=_doc(name="Call of Duty, Xbox"))
    assert r.status_code == 201, r.text
    v = client.get(f"/profiles/{r.json()['id']}/validate").json()
    assert v["errors"] == 0 and any("comma" in f["message"] for f in v["findings"] if f["severity"] == "warning")
    for bad in ("Call of\nDuty", "Call of Dut\u00fd"):
        assert client.post("/profiles", json=_doc(name=bad)).status_code == 422, bad
        assert client.patch(f"/profiles/{r.json()['id']}", json={"name": bad}).status_code == 422, bad
        assert client.patch(f"/profiles/{r.json()['id']}", json={"source_url": f"https://x/{bad}"}).status_code == 422
        assert client.post(f"/profiles/{r.json()['id']}/convert", json={"target": "xbox", "name": bad}).status_code == 422
        assert client.post(f"/profiles/{r.json()['id']}/duplicate", params={"name": bad}).status_code == 422
    assert client.post(f"/profiles/{r.json()['id']}/duplicate", params={"name": "Copy, mine"}).status_code == 201


def test_a_game_action_naming_a_mode_follows_the_mode_rule(client):
    p = client.post("/profiles", json=_doc()).json()
    ga = [{"output": "right_2", "action": "Fire, hold", "mode_name": "M"}]     # the label is card-only
    assert client.patch(f"/profiles/{p['id']}", json={"game_actions": ga}).status_code == 200
    ga[0]["mode_name"] = "M,1"
    assert client.patch(f"/profiles/{p['id']}", json={"game_actions": ga}).status_code == 422


def test_the_fixtures_still_read_back_and_save(client):
    for name in ("ddfortnite.csv", "cod.csv", "synthetic_pref_override.csv"):
        p = upload(client, FIXTURES / name)["profile"]
        doc = client.get(f"/profiles/{p['id']}").json()
        assert client.put(f"/profiles/{p['id']}", json=doc).status_code == 200, name
