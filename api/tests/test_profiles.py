import json
import re
import pytest
from qsprofile import catalog as C
from qsprofile import load
from conftest import FIXTURES, ACTIONS, upload
from app.seed import seed_fixtures, FIXTURES as SEED_FIXTURES


def test_catalog_comes_from_the_core_module(client):
    cat = client.get("/catalog").json()
    inputs = {i["name"]: i for i in cat["inputs"]}
    outputs = {o["name"]: o for o in cat["outputs"]}
    assert set(C.all_mouthpiece_inputs()) <= set(inputs)
    assert inputs["digital_in_7"]["jack"] == C.DIGITAL_JACKS[7]
    assert inputs["lip"]["kind"] == "lip"
    assert set(C.OUTPUTS) <= set(outputs)
    assert outputs["x"]["xbox_name"] == "A" and outputs["x"]["ps_glyph"] == "✕"
    assert {f["name"] for f in cat["functions"]} == set(C.FUNCTIONS)
    assert cat["digital_jacks"]["1"] == C.DIGITAL_JACKS[1]
    assert cat["xbox_to_ps"] == C.XBOX_TO_PS
    assert "kb_a" in outputs and outputs["kb_a"]["grp"] == "keyboard"


def test_crud_roundtrip_and_canonical_storage(client):
    body = {
        "name": "Test", "csv_filename": "test.csv", "game": "Fortnite", "console": "xbox",
        "modes": [{"name": "Left", "label": "Left joy", "mappings": [
            {"output": "right_2", "function": "normal", "inputs": ["mp_center_puff"]},
            {"output": "increment_mode", "inputs": ["right_sip"]},
            {"output": "left_joy_up", "inputs": ["up"]},
            {"output": "x", "function": "repeat", "params": [5, 2000], "inputs": ["lip"], "comment": "jump"},
        ]}],
        "preferences": {"digital_out_1": "1"},
        "input_names": {"lip": "Chin switch"},
        "game_actions": [{"output": "right_2", "action": "Fire"}],
    }
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["modes"][0]["position"] == 1
    assert p["modes"][0]["mappings"][3]["params"] == [5, 2000]
    assert p["modes"][0]["mappings"][3]["row"] == 7
    assert p["input_names"] == {"lip": "Chin switch"}
    # stored canonically: output is 'right_2' even though the profile is Xbox
    assert p["modes"][0]["mappings"][0]["output"] == "right_2"
    # ...and exported under the Xbox name
    csv = client.get(f"/profiles/{p['id']}/export.csv").content.decode()
    assert "XBox Outputs,Function,usb," in csv and "right_trigger,normal,mp_center_puff," in csv

    lst = client.get("/profiles", params={"validate": "true"}).json()
    assert [x["id"] for x in lst] == [p["id"]] and lst[0]["mode_count"] == 1
    assert lst[0]["validation"]["errors"] == 0

    r = client.patch(f"/profiles/{p['id']}", json={"input_names": {"lip": "Cheek"}})
    assert r.status_code == 200 and r.json()["input_names"] == {"lip": "Cheek"}

    # the emulation mode is a row in the file's Preferences block, nothing else
    body["modes"].append({"name": "Right", "label": "Right joy", "mappings": []})
    body["preferences"]["enable_DS3_emulation"] = "5"
    r = client.put(f"/profiles/{p['id']}", json=body)
    assert r.status_code == 200 and [m["position"] for m in r.json()["modes"]] == [1, 2]
    assert r.json()["preferences"]["enable_DS3_emulation"] == "5"
    v = client.get(f"/profiles/{p['id']}/validate").json()
    assert any("hides the flash drive" in f["message"] for f in v["findings"])

    assert client.delete(f"/profiles/{p['id']}").status_code == 204
    assert client.get(f"/profiles/{p['id']}").status_code == 404


def test_keywords_outside_the_catalog_are_rejected(client):
    base = {"name": "T", "csv_filename": "t.csv"}
    for mapping in ({"output": "fire", "inputs": ["lip"]},
                    {"output": "x", "inputs": ["chin"]},
                    {"output": "x", "function": "hold", "inputs": ["lip"]},
                    {"output": "A", "inputs": ["lip"]}):          # Xbox name is not canonical
        r = client.post("/profiles", json={**base, "modes": [{"name": "M", "mappings": [mapping]}]})
        assert r.status_code == 422, mapping
    # a parameter the function does not take is stored as the file would say it and
    # reported by core against the row; an import keeps such a row, so a save must too
    r = client.post("/profiles", json={**base, "modes": [{"name": "M", "mappings": [
        {"output": "x", "function": "toggle", "params": [1], "inputs": ["lip"]}]}]})
    assert r.status_code == 201, r.text
    v = client.get(f"/profiles/{r.json()['id']}/validate").json()
    assert any("takes at most 0 parameter" in f["message"] and f["severity"] == "error" for f in v["findings"])
    assert client.get(f"/profiles/{r.json()['id']}/export.csv").status_code == 409
    assert client.post("/profiles", json={**base, "input_names": {"chin": "x"}}).status_code == 422
    assert client.post("/profiles", json={"name": "T", "csv_filename": "bad name.csv"}).status_code == 422
    # regex families are valid and get added to the catalog on first use
    r = client.post("/profiles", json={**base, "modes": [{"name": "M", "mappings": [
        {"output": "kb_numpad_7", "inputs": ["lip"]}]}]})
    assert r.status_code == 201, r.text
    assert any(o["name"] == "kb_numpad_7" for o in client.get("/catalog").json()["outputs"])


def test_convert_creates_a_copy_and_is_lossless(client):
    src = upload(client, FIXTURES / "Call_of_Duty_Advanced_Warfare_XBox_One.xlsx")["profile"]
    r = client.post(f"/profiles/{src['id']}/convert", json={"target": "playstation"})
    assert r.status_code == 201, r.text
    ps = r.json()
    assert ps["notes"] == [] and ps["suggested_csv_filename"].endswith("_ps.csv")
    assert ps["profile"]["console"] == "playstation" and ps["profile"]["id"] != src["id"]
    csv = client.get(f"/profiles/{ps['profile']['id']}/export.csv").content.decode()
    assert "Output or Function,Function,usb," in csv and "right_trigger" not in csv
    r = client.post(f"/profiles/{ps['profile']['id']}/convert", json={"target": "xbox", "csv_filename": "back.csv"})
    back = r.json()["profile"]
    strip = lambda p: [(m["output"], m["function"], m["params"], m["inputs"])
                       for md in p["modes"] for m in md["mappings"]]
    assert strip(back) == strip(src)
    assert len(client.get("/profiles").json()) == 3


def test_a_name_that_differs_from_the_filename_is_not_reported_at_all(client):
    """Owner's decision, 2026-09-15: the device loads by filename and never reads the
    name, so a friendly label beside a short device filename is correct, not a fault.
    It saves unrewritten, reports nothing at any severity, and exports."""
    body = {"name": "My Loadout", "csv_filename": "cvcodww2.csv", "modes": [{"name": "M", "mappings": [
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]}
    p = client.post("/profiles", json=body).json()
    assert p["name"] == "My Loadout" and p["csv_filename"] == "cvcodww2.csv"   # not rewritten
    r = client.put(f"/profiles/{p['id']}", json=body)
    assert r.status_code == 200, r.text
    v = client.get(f"/profiles/{p['id']}/validate").json()
    assert not [f for f in v["findings"] if "My Loadout" in f["message"]], v["findings"]
    assert v["errors"] == 0
    assert client.get(f"/profiles/{p['id']}/export.csv").status_code == 200
    assert client.get(f"/profiles/{p['id']}/export.xlsx").status_code == 200


def test_convert_to_xbox_warns_about_touch(client):
    """The touchpad *press* has an Xbox name (capture), so ddfortnite converts
    without notes; only the swipes (touch_up/down/left/right) have no equivalent."""
    p = upload(client, FIXTURES / "ddfortnite.xlsx")["profile"]
    assert any(m["output"] == "touch" for md in p["modes"] for m in md["mappings"])
    r = client.post(f"/profiles/{p['id']}/convert", json={"target": "xbox"})
    assert r.status_code == 201, r.text
    assert r.json()["notes"] == []
    csv = client.get(f"/profiles/{r.json()['profile']['id']}/export.csv").content.decode()
    assert "capture,normal," in csv and "\ntouch," not in csv

    body = {"name": "Swipe", "csv_filename": "swipe.csv", "modes": [{"name": "M", "mappings": [
        {"output": "touch_up", "inputs": ["lip"]},
        {"output": "increment_mode", "inputs": ["right_sip"]},
    ]}]}
    p = client.post("/profiles", json=body).json()
    r = client.post(f"/profiles/{p['id']}/convert", json={"target": "xbox"})
    assert r.status_code == 201, r.text
    assert [(n["mode"], n["row"]) for n in r.json()["notes"]] == [(1, 4)]
    assert "touch_up" in r.json()["notes"][0]["message"] and "no Xbox equivalent" in r.json()["notes"][0]["message"]


def test_card_uses_game_actions_and_input_names(client):
    actions = json.loads((ACTIONS / "actions_fortnite.json").read_text())
    p = upload(client, FIXTURES / "ddfortnite.csv", game="Fortnite")["profile"]
    html = client.get(f"/profiles/{p['id']}/card.html").text
    assert "Fortnite" in html and "Aim down sights" in html      # from the shared template
    assert "Chin switch" not in html
    r = client.patch(f"/profiles/{p['id']}", json={"input_names": actions["inputs"]})
    assert r.status_code == 200
    html = client.get(f"/profiles/{p['id']}/card.html").text
    assert "Chin switch" in html
    assert "text/html" in client.get(f"/profiles/{p['id']}/card.html").headers["content-type"]


def test_summary_is_three_columns_of_the_same_facts(client):
    p = upload(client, FIXTURES / "ddfortnite.csv", game="Fortnite")["profile"]
    html = client.get(f"/profiles/{p['id']}/summary.html").text
    # the per-mode headings: game name first, PS names third, the note last
    assert "<th>Fortnite</th><th>QuadStick</th><th>PS5</th><th>Note</th>" in html
    assert "Aim down sights" in html and "Center sip" in html
    # compact by construction: no mouthpiece diagram and no tube grid
    assert "<svg" not in html and 'class="grid"' not in html

    r = client.post(f"/profiles/{p['id']}/convert", json={"target": "xbox"})
    xbox = client.get(f"/profiles/{r.json()['profile']['id']}/summary.html").text
    assert "<th>Xbox</th>" in xbox


def test_summary_opens_with_every_command_once(client):
    """Page 1 collapses the repeats; the per-mode tables below keep them."""
    p = upload(client, FIXTURES / "ddfortnite.csv", game="Fortnite")["profile"]
    html = client.get(f"/profiles/{p['id']}/summary.html").text

    overview = html[html.index('class="page summary overview"'):html.index('<div class="modebar"')]
    # the game action leads; the mode dots sit third, between QuadStick and PS5
    assert "<th>Fortnite</th><th>QuadStick</th><th>Mode</th><th>PS5</th>" in overview

    # 158 active rows across 7 modes, but only 54 distinct commands
    assert overview.count('<td class="dots">') == 54

    # Fire appears 7 times below — once per mode — but the overview keeps only the
    # three genuinely different ways to do it, not one line per mode.
    assert html[html.index('<div class="modebar"'):].count(">Fire<") == 7
    fire = re.findall(r"<tr>(?:(?!</tr>).)*?>Fire<.*?</tr>", overview, re.S)
    assert len(fire) == 3

    # Center puff fires in modes 1, 2, 3 and 7: one dot per mode, lit where it works
    row = next(r for r in fire if "Center puff" in r)
    dots = re.findall(r'<i class="(on)?"></i>', row)
    assert len(dots) == 7
    assert [i + 1 for i, d in enumerate(dots) if d] == [1, 2, 3, 7]
    assert "Modes 1, 2, 3, 7" in row


def test_seed_imports_every_fixture(client, db):
    imported = seed_fixtures(db, FIXTURES, ACTIONS)
    assert len(imported) == len(SEED_FIXTURES) == 6      # 5 real + synthetic_pref_override.csv
    assert seed_fixtures(db, FIXTURES, ACTIONS) == []             # idempotent

    # the library shows the owner's own profiles; the starter ones are a separate shelf
    lst = client.get("/profiles", params={"validate": "true"}).json()
    templates = client.get("/profiles", params={"templates": "true", "validate": "true"}).json()
    assert len(lst) + len(templates) == 6
    assert len(templates) == 3            # the three .xlsx starters
    assert all(x["validation"]["errors"] == 0 for x in lst + templates)
    assert all(not x["is_template"] for x in lst)
    assert all(x["is_template"] and x["template_note"] for x in templates)

    by_name = {x["name"]: x for x in lst + templates}
    # the summary's emulation_mode is derived from the file's own enable_DS3_emulation
    # row; none of the fixtures carries one (the owner's device takes it from prefs.csv),
    # and the seed adds nothing so the device CSVs stay byte-identical (decision D1)
    assert all(x["emulation_mode"] is None for x in lst + templates)
    assert "emulation_mode" not in client.get(f"/profiles/{by_name['ddfortnite']['id']}").json()
    assert all(x["firmware"] == 2373 for x in lst + templates)
    # his live device CSVs are profiles, not starters, because a re-export of one
    # must stay byte-identical to the file on the flash drive
    assert not by_name["ddfortnite"]["is_template"]
    assert not by_name["Call of Duty"]["is_template"]
    fort = next(x for x in lst if x["name"] == "ddfortnite")
    detail = client.get(f"/profiles/{fort['id']}").json()
    assert detail["input_names"]["lip"] == "Chin switch"
    assert any(g["output"] == "right_2" and g["action"] == "Fire" for g in detail["game_actions"])
    assert any(g["mode_name"] == "Sprint" for g in detail["game_actions"])
    for x in lst + templates:
        assert client.get(f"/profiles/{x['id']}/export.csv").status_code == 200
        assert client.get(f"/profiles/{x['id']}/card.html").status_code == 200


def test_a_child_only_patch_bumps_updated_at_and_reorders_the_library(client):
    """The library sorts by updated_at. A game-action or input-name edit touches no
    profiles column, so the row's own onupdate never fired and the order went stale."""
    older = upload(client, FIXTURES / "cod.csv")["profile"]
    newer = upload(client, FIXTURES / "ddfortnite.csv")["profile"]
    assert [x["id"] for x in client.get("/profiles").json()] == [newer["id"], older["id"]]

    r = client.patch(f"/profiles/{older['id']}", json={"game_actions": [{"output": "x", "action": "Jump"}]})
    assert r.status_code == 200, r.text
    assert r.json()["updated_at"] > older["updated_at"]
    assert [x["id"] for x in client.get("/profiles").json()] == [older["id"], newer["id"]]

    # and a PUT of the whole document moves the other one back to the top
    doc = client.get(f"/profiles/{newer['id']}").json()
    r = client.put(f"/profiles/{newer['id']}", json=doc)
    assert r.status_code == 200, r.text
    assert r.json()["updated_at"] > newer["updated_at"]
    assert [x["id"] for x in client.get("/profiles").json()] == [newer["id"], older["id"]]


def test_a_game_action_for_an_unknown_output_is_refused(client):
    """Game actions label outputs on the card; a label for a keyword the device does
    not have (or an Xbox name, which is not canonical) can never match a row."""
    base = {"name": "GA", "csv_filename": "ga.csv"}
    p = client.post("/profiles", json=base).json()
    for bad in ("fire", "A", "right_trigger", ""):
        ga = [{"output": bad, "action": "Fire"}]
        assert client.post("/profiles", json={**base, "game_actions": ga}).status_code == 422, bad
        assert client.patch(f"/profiles/{p['id']}", json={"game_actions": ga}).status_code == 422, bad
        assert client.put(f"/profiles/{p['id']}", json={**base, "game_actions": ga}).status_code == 422, bad
    assert client.get(f"/profiles/{p['id']}").json()["game_actions"] == []
    # canonical names and the regex families are fine
    ga = [{"output": "right_2", "action": "Fire"}, {"output": "kb_numpad_5", "action": "Map", "mode_name": "M"}]
    r = client.patch(f"/profiles/{p['id']}", json={"game_actions": ga})
    assert r.status_code == 200, r.text
    assert [(g["output"], g["action"], g["mode_name"]) for g in r.json()["game_actions"]] == \
           [("right_2", "Fire", None), ("kb_numpad_5", "Map", "M")]


# ---------------------------------------------------------------- PATCH nulls (W1)
@pytest.mark.parametrize("field", ["name", "csv_filename", "console", "firmware", "is_template"])
def test_patch_with_an_explicit_null_on_a_required_field_is_a_422(client, field):
    """`{"csv_filename": null}` used to reach the column and fail NOT NULL as a 500.
    Null is not a reset: PUT is the path that rewrites a whole profile."""
    p = client.post("/profiles", json={"name": "Nulls", "csv_filename": "nulls.csv"}).json()
    before = client.get(f"/profiles/{p['id']}").json()
    r = client.patch(f"/profiles/{p['id']}", json={field: None})
    assert r.status_code == 422, (field, r.text)
    assert field in r.text and "omit the field" in r.text
    assert client.get(f"/profiles/{p['id']}").json()[field] == before[field]


def test_patch_names_every_required_field_that_was_sent_as_null(client):
    p = client.post("/profiles", json={"name": "Nulls", "csv_filename": "nulls2.csv"}).json()
    r = client.patch(f"/profiles/{p['id']}", json={"name": None, "firmware": None, "game": None})
    assert r.status_code == 422, r.text
    assert "name" in r.text and "firmware" in r.text


@pytest.mark.parametrize("field", ["game", "notes", "source_url", "template_note"])
def test_patch_with_a_null_on_a_nullable_field_clears_it(client, field):
    p = client.post("/profiles", json={"name": "Nulls", "csv_filename": "nulls3.csv",
                                       field: "something"}).json()
    assert p[field] == "something"
    r = client.patch(f"/profiles/{p['id']}", json={field: None})
    assert r.status_code == 200, (field, r.text)
    assert client.get(f"/profiles/{p['id']}").json()[field] is None


def test_an_empty_patch_changes_nothing(client):
    p = client.post("/profiles", json={"name": "Nulls", "csv_filename": "nulls4.csv"}).json()
    r = client.patch(f"/profiles/{p['id']}", json={})
    assert r.status_code == 200, r.text
    for k in ("name", "csv_filename", "console", "firmware", "is_template"):
        assert r.json()[k] == p[k]


# ---------------------------------------------------------------- firmware (W19)
def test_an_unknown_firmware_is_refused_the_same_way_everywhere(client):
    body = {"name": "FW", "csv_filename": "fw.csv", "firmware": 9999}
    r = client.post("/profiles", json=body)
    assert r.status_code == 422 and "Unknown firmware 9999" in r.text and "2373" in r.text
    p = client.post("/profiles", json={**body, "firmware": 1476}).json()
    assert p["firmware"] == 1476
    r = client.patch(f"/profiles/{p['id']}", json={"firmware": 9999})
    assert r.status_code == 422 and "Unknown firmware 9999" in r.text
    # a PATCH that leaves firmware out keeps it
    assert client.patch(f"/profiles/{p['id']}", json={"game": "X"}).json()["firmware"] == 1476
    r = client.post("/profiles/validate", json={"name": "FW", "csv_filename": "fw.csv", "firmware": 9999})
    assert r.status_code == 422 and "Unknown firmware 9999" in r.text
    r = client.get("/prefs", params={"firmware": 9999})
    assert r.status_code == 422 and "Unknown firmware 9999" in r.text


# ---------------------------------------------------------------- library search (N1)
def test_library_search_treats_the_wildcards_as_ordinary_characters(client):
    """`_` and `%` are LIKE wildcards; a search for one used to match every profile."""
    for name, game, fn in (("Fortnite", "Fortnite", "fn.csv"),
                           ("COD", "Call of Duty", "cod.csv"),
                           ("Odd", "a_b", "odd.csv"),
                           ("Pct", "100% aim", "pct.csv")):
        assert client.post("/profiles", json={"name": name, "game": game,
                                              "csv_filename": fn}).status_code == 201

    def names(q):
        return sorted(p["name"] for p in client.get("/profiles", params={"q": q}).json())

    assert names("_") == ["Odd"]
    assert names("%") == ["Pct"]
    assert names("a_b") == ["Odd"]
    assert names("FORT") == ["Fortnite"]          # still case-insensitive
    assert names("of du") == ["COD"]
    assert names("zzz") == []


# ---------------------------------------------------------------- check / save parity (W18)
def test_the_live_check_and_the_save_build_the_same_rows(client):
    """W18: the live check used to have its own copy of the row builder, so the two
    could drift. The same document through both paths must give the same findings."""
    doc = {
        "name": "Parity", "csv_filename": "parity.csv", "firmware": 2373,
        "modes": [{"name": "Left", "label": "Left joy", "channel": "both", "mappings": [
            {"output": "increment_mode", "inputs": ["right_sip"]},
            {"output": "x", "function": "repeat", "params": [5, 2000], "inputs": ["lip"],
             "comment": "never exported"},
            {"kind": "preference", "output": "sip_puff_threshold", "value": "55"},
            {"output": "left_joy_up", "inputs": ["up", "down"]},     # a sequence
        ]}],
        "preferences": {"digital_out_1": "1"},
    }
    live = client.post("/profiles/validate", json=doc)
    assert live.status_code == 200, live.text
    saved = client.post("/profiles", json=doc)
    assert saved.status_code == 201, saved.text
    stored = client.get(f"/profiles/{saved.json()['id']}/validate")
    assert stored.status_code == 200, stored.text
    assert live.json()["findings"] == stored.json()["findings"]
    assert live.json()["budget"] == stored.json()["budget"]


def test_the_eight_input_cap_is_the_same_on_the_check_and_the_save(client):
    """A sequence of 9 is a bad request on both paths, and 8 goes through on both."""
    def doc(n):
        return {"name": "Cap", "csv_filename": "cap.csv", "modes": [{"name": "M", "mappings": [
            {"output": "x", "inputs": ["lip"] * n}]}]}

    assert client.post("/profiles/validate", json=doc(9)).status_code == 422
    assert client.post("/profiles", json=doc(9)).status_code == 422
    assert client.post("/profiles/validate", json=doc(8)).status_code == 200
    r = client.post("/profiles", json=doc(8))
    assert r.status_code == 201, r.text
    row = client.get(f"/profiles/{r.json()['id']}").json()["modes"][0]["mappings"][0]
    assert len(row["inputs"]) == 8 and row["is_sequence"] is True


def test_the_live_check_persists_nothing(client):
    """The check path passes no session, so no output row may be created by it."""
    before = client.get("/catalog").json()["outputs"]
    r = client.post("/profiles/validate", json={"name": "K", "csv_filename": "k.csv", "modes": [
        {"name": "M", "mappings": [{"output": "kb_numpad_5", "inputs": ["lip"]}]}]})
    assert r.status_code == 200, r.text
    assert client.get("/profiles").json() == []
    assert client.get("/catalog").json()["outputs"] == before
