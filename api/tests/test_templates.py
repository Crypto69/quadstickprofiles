"""Starter profiles: a profile flagged is_template, so "new from template" reuses
the copy path rather than being a second kind of thing to keep in step."""
from qsprofile import load, write_csv
from conftest import ACTIONS, FIXTURES, upload
from app.seed import seed_fixtures, FIXTURES as SEED_FIXTURES


def _template(client, name="FPS starter", note="Five modes"):
    body = {"name": name, "csv_filename": "fpsstarter.csv", "game": "Shooter",
            "is_template": True, "template_note": note,
            "modes": [{"name": "Left", "label": "Left joy", "mappings": [
                {"output": "increment_mode", "inputs": ["right_sip"]},
                {"output": "left_joy_up", "inputs": ["up"]},
                {"output": "right_2", "inputs": ["mp_center_sip"]},
            ]}],
            "preferences": {"mouse_speed": "120"},
            "input_names": {"lip": "Chin switch"},
            "game_actions": [{"output": "right_2", "action": "Fire"}]}
    r = client.post("/profiles", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_templates_are_a_separate_shelf(client):
    _template(client)
    client.post("/profiles", json={"name": "Mine", "csv_filename": "mine.csv"})

    library = client.get("/profiles").json()
    templates = client.get("/profiles", params={"templates": "true"}).json()
    assert [p["name"] for p in library] == ["Mine"]
    assert [p["name"] for p in templates] == ["FPS starter"]
    assert templates[0]["template_note"] == "Five modes"


def test_new_from_template_copies_everything_but_the_identity(client):
    t = _template(client)
    r = client.post(f"/profiles/from-template/{t['id']}",
                    json={"name": "My shooter", "csv_filename": "myshooter.csv"})
    assert r.status_code == 201, r.text
    new = r.json()

    # its own identity
    assert new["id"] != t["id"]
    assert new["name"] == "My shooter"
    assert new["csv_filename"] == "myshooter.csv"
    # and it is not itself a starter any more
    assert new["is_template"] is False
    assert new["template_note"] is None
    assert "starter profile" in new["notes"]

    # everything worth copying came across
    assert len(new["modes"]) == len(t["modes"])
    assert [m["output"] for m in new["modes"][0]["mappings"]] == \
           [m["output"] for m in t["modes"][0]["mappings"]]
    assert new["preferences"] == {"mouse_speed": "120"}
    assert new["input_names"] == {"lip": "Chin switch"}
    assert any(g["output"] == "right_2" and g["action"] == "Fire" for g in new["game_actions"])
    assert new["firmware"] == t["firmware"]
    # and it shows up in the library, not on the starter shelf
    assert "My shooter" in [p["name"] for p in client.get("/profiles").json()]
    assert "My shooter" not in [p["name"] for p in
                                client.get("/profiles", params={"templates": "true"}).json()]


def test_a_profile_started_from_a_template_exports(client):
    t = _template(client)
    new = client.post(f"/profiles/from-template/{t['id']}",
                      json={"name": "My shooter", "csv_filename": "myshooter.csv"}).json()
    r = client.get(f"/profiles/{new['id']}/export.csv")
    assert r.status_code == 200
    csv = r.content.decode()
    assert "myshooter.csv,,Normal," in csv        # its own filename, not the template's
    assert "fpsstarter.csv" not in csv


def test_from_template_refuses_an_ordinary_profile(client):
    p = client.post("/profiles", json={"name": "Mine", "csv_filename": "mine.csv"}).json()
    r = client.post(f"/profiles/from-template/{p['id']}",
                    json={"name": "Copy", "csv_filename": "copy.csv"})
    assert r.status_code == 409
    assert "not a starter profile" in r.json()["detail"]
    assert client.post("/profiles/from-template/999999",
                       json={"name": "x", "csv_filename": "x.csv"}).status_code == 404


def test_from_template_needs_a_valid_filename(client):
    t = _template(client)
    for bad in ("bad name.csv", "nodotcsv", "has,comma.csv"):
        r = client.post(f"/profiles/from-template/{t['id']}",
                        json={"name": "x", "csv_filename": bad})
        assert r.status_code == 422, bad


def test_a_template_can_be_promoted_or_demoted(client):
    p = client.post("/profiles", json={"name": "Mine", "csv_filename": "mine.csv"}).json()
    r = client.patch(f"/profiles/{p['id']}",
                     json={"is_template": True, "template_note": "Turned out useful"})
    assert r.status_code == 200
    assert r.json()["is_template"] is True
    assert [x["name"] for x in client.get("/profiles", params={"templates": "true"}).json()] == ["Mine"]
    assert client.get("/profiles").json() == []

    client.patch(f"/profiles/{p['id']}", json={"is_template": False})
    assert [x["name"] for x in client.get("/profiles").json()] == ["Mine"]


def test_duplicating_a_template_keeps_it_a_template(client):
    """Duplicate means "another one of these", so a copy of a starter is a starter.
    Starting *from* one is the other endpoint."""
    t = _template(client)
    copy = client.post(f"/profiles/{t['id']}/duplicate").json()
    assert copy["is_template"] is True
    assert copy["template_note"] == "Five modes"


def test_the_seeded_starters_are_usable_as_starters(client, db):
    seed_fixtures(db, FIXTURES, ACTIONS)
    templates = client.get("/profiles", params={"templates": "true"}).json()
    assert len(templates) == 3
    for t in templates:
        r = client.post(f"/profiles/from-template/{t['id']}",
                        json={"name": f"From {t['name']}", "csv_filename": "fromstarter.csv"})
        assert r.status_code == 201, r.text
        new = r.json()
        assert len(new["modes"]) == t["mode_count"]
        assert new["game_actions"], "a starter should bring its game-action labels"
        # and the result is clean enough to export
        assert client.get(f"/profiles/{new['id']}/export.csv").status_code == 200
        client.delete(f"/profiles/{new['id']}")


def test_the_seeded_starters_export_their_fixture_bytes(client, db, tmp_path):
    """Seeding is import plus a display name: what a starter exports must be exactly
    what core writes for its fixture, and for the two starters that came from the
    owner's own sheets, exactly the device file once the sheet title and URL (which
    the download does not carry) are set, as tests/test_roundtrip.py proves for core."""
    seed_fixtures(db, FIXTURES, ACTIONS)
    templates = {t["name"]: t for t in client.get("/profiles", params={"templates": "true"}).json()}
    for fname, (_actions, display, note) in SEED_FIXTURES.items():
        if not note:
            continue
        cfg, _ = load(str(FIXTURES / fname))
        cfg.name = display
        out = tmp_path / f"{display}.csv"
        write_csv(cfg, str(out))
        r = client.get(f"/profiles/{templates[display]['id']}/export.csv")
        assert r.status_code == 200, (fname, r.text)
        assert r.content == out.read_bytes(), fname
    for xlsx, csvname in (("ddfortnite.xlsx", "ddfortnite.csv"), ("Call_of_Duty.xlsx", "cod.csv")):
        real, _ = load(str(FIXTURES / csvname))
        t = templates[SEED_FIXTURES[xlsx][1]]
        r = client.patch(f"/profiles/{t['id']}", json={"name": real.name, "source_url": real.source_url})
        assert r.status_code == 200, r.text
        assert client.get(f"/profiles/{t['id']}/export.csv").content == (FIXTURES / csvname).read_bytes()
    # and the device CSVs seeded as ordinary profiles differ from the stick only by display name
    library = {p["name"]: p for p in client.get("/profiles").json()}
    for fname, (_actions, display, note) in SEED_FIXTURES.items():
        if note or not fname.endswith(".csv"):
            continue
        real, _ = load(str(FIXTURES / fname))
        pid = library[display]["id"]
        assert client.patch(f"/profiles/{pid}", json={"name": real.name}).status_code == 200
        assert client.get(f"/profiles/{pid}/export.csv").content == (FIXTURES / fname).read_bytes(), fname


def test_an_imported_profile_is_not_a_template(client):
    got = upload(client, FIXTURES / "cod.csv")
    assert got["profile"]["is_template"] is False


def test_the_three_copy_paths_all_carry_the_preferences_and_the_labels(client):
    """N3: the labels are copied by hand (they are not part of the Config); the
    preferences and the mode rows ride along with it. All three must agree."""
    t = _template(client)
    made = [
        client.post(f"/profiles/from-template/{t['id']}",
                    json={"name": "From template", "csv_filename": "ft.csv"}).json(),
        client.post(f"/profiles/{t['id']}/duplicate").json(),
        client.post(f"/profiles/{t['id']}/convert", json={"target": "xbox"}).json()["profile"],
    ]
    for new in made:
        assert new["preferences"] == {"mouse_speed": "120"}, new["name"]
        assert new["input_names"] == {"lip": "Chin switch"}, new["name"]
        assert [(g["output"], g["action"]) for g in new["game_actions"]] == [("right_2", "Fire")], new["name"]
        assert [m["output"] for m in new["modes"][0]["mappings"]] == \
               [m["output"] for m in t["modes"][0]["mappings"]], new["name"]
        # one row each, not two: the preferences are copied once
        assert len(new["preferences"]) == 1 and len(new["input_names"]) == 1
        assert len(new["game_actions"]) == 1
