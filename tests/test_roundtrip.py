"""Baseline the handover relies on: every fixture round-trips byte-for-byte.
Run: cd core && pip install -e ".[dev]" && cd .. && pytest -q"""
import pathlib
import pytest
from qsprofile import load, validate, convert, write_csv

FX = pathlib.Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize("name", ["ddfortnite.csv", "cod.csv"])
def test_device_csv_roundtrip_is_identical(name, tmp_path):
    cfg, _ = load(str(FX / name))
    out = tmp_path / name
    write_csv(cfg, str(out))
    assert out.read_bytes() == (FX / name).read_bytes()


@pytest.mark.parametrize("xlsx,csvname,title", [
    ("ddfortnite.xlsx", "ddfortnite.csv", "ddfortnite"),
    ("Call_of_Duty.xlsx", "cod.csv", "Call of Duty"),
])
def test_google_sheet_xlsx_exports_the_same_csv_as_the_addon(xlsx, csvname, title, tmp_path):
    cfg, _ = load(str(FX / xlsx))
    cfg.name = title
    real, _ = load(str(FX / csvname))
    out = tmp_path / csvname
    write_csv(cfg, str(out), source_url=real.source_url)
    assert out.read_bytes() == (FX / csvname).read_bytes()


def test_xbox_to_playstation_and_back_is_lossless():
    cfg, _ = load(str(FX / "Call_of_Duty_Advanced_Warfare_XBox_One.xlsx"))
    assert cfg.console == "xbox"
    ps, notes = convert(cfg, "playstation")
    assert ps.console == "playstation" and not notes
    back, _ = convert(ps, "xbox")
    for a, b in zip(cfg.modes, back.modes):
        assert [(m.output, m.function, m.params, m.inputs) for m in a.mappings] == \
               [(m.output, m.function, m.params, m.inputs) for m in b.mappings]


def test_fixtures_have_no_validation_errors():
    for f in FX.iterdir():
        cfg, problems = load(str(f))
        assert not [p for p in validate(cfg, problems) if p[0] == "error"], f.name


def test_validator_catches_known_fortnite_issues():
    cfg, problems = load(str(FX / "ddfortnite.xlsx"))
    findings = validate(cfg, problems)
    warnings = [p[3] for p in findings if p[0] == "warning"]
    assert any("destiny.csv" in m for m in warnings)
    # An input that fires an action and changes mode in the same press is a
    # deliberate design, not a fault, so it is described, not warned about.
    notes = [p[3] for p in findings if p[0] == "info"]
    assert any("mp_center_sip" in m and "increment_mode" in m for m in notes)
    assert not any("increment_mode" in m and "at the same moment" in m for m in warnings)


# ---------------------------------------------------------------- hygiene (0.5)
def test_write_csv_never_emits_trailing_spaces(tmp_path):
    """The device keeps trailing spaces inside a keyword, so an export that carried
    one would silently stop matching. No exported line may end in a space."""
    for name in ["ddfortnite.csv", "cod.csv", "synthetic_pref_override.csv"]:
        cfg, _ = load(str(FX / name))
        out = tmp_path / name
        write_csv(cfg, str(out))
        for i, line in enumerate(out.read_bytes().split(b"\r\n"), start=1):
            assert not line.endswith(b" "), f"{name} line {i} ends in a space: {line!r}"
            for cell in line.split(b","):
                assert cell == cell.strip(), f"{name} line {i} has a padded cell {cell!r}"


def test_hygiene_reports_whitespace_and_embedded_newlines(tmp_path):
    """A cell with a trailing space is repaired with an info; a quoted newline is
    joined with a warning, because the device would read it as an early blank row."""
    src = tmp_path / "messy.csv"
    src.write_bytes(
        b"QuadStick Configuration,Version 1.4,,Messy\r\n"
        b"Profile Name,,Left joy,\r\n"
        b"messy.csv,,Normal,\r\n"
        b"Output or Function,Function,usb,\r\n"
        b"increment_mode,normal,right_sip ,\r\n"          # trailing space in an input
        b'"x\ncross",normal,lip,\r\n'                     # embedded newline in the output
        b"\r\n"
    )
    cfg, problems = load(str(src))
    infos = [p for p in problems if p[0] == "info" and "whitespace" in p[3]]
    warns = [p for p in problems if p[0] == "warning" and "line break" in p[3]]
    assert infos, problems
    assert warns, problems
    assert cfg.modes[0].mappings[0].inputs == ["right_sip"]     # repaired, not "right_sip "


# ---------------------------------------------------------------- per-mode preference overrides (0.7)
def test_preference_override_row_roundtrips_and_is_flagged():
    """fixtures/synthetic_pref_override.csv is hand-built, not off a device:
    mode 2 sets sip_puff_threshold and mouse_speed for that mode only."""
    cfg, problems = load(str(FX / "synthetic_pref_override.csv"))
    overrides = [m for m in cfg.modes[1].mappings if m.kind == "preference"]
    assert [(m.output, m.value) for m in overrides] == [("sip_puff_threshold", "55"), ("mouse_speed", "120")]
    assert all(not m.inputs and not m.is_sequence() for m in overrides)
    findings = validate(cfg, problems)
    assert not [f for f in findings if f[0] == "error"]
    # A per-mode override is a documented feature, so it is described rather than
    # warned about: the "not verified" part is a gap in this app's knowledge, not
    # something wrong with the profile.
    msgs = [f[3] for f in findings if f[0] == "info"]
    assert any("sip_puff_threshold = 55 for this mode only" in m for m in msgs)
    assert any("not yet verified on a device" in m for m in msgs)
    assert not [f for f in findings if f[0] == "warning" and "for this mode only" in f[3]]


def test_preference_override_shows_on_the_card():
    from qsprofile import render
    cfg, problems = load(str(FX / "synthetic_pref_override.csv"))
    html = render(cfg, {"game": "Test", "outputs": {}, "modes": {}, "inputs": {}}, validate(cfg, problems))
    assert "Settings in this mode" in html
    assert "sip_puff_threshold" in html and "55" in html


def test_card_embeds_the_front_photo_and_labels_every_part():
    """The card is one standalone HTML file, so the photo has to travel inside it.

    A missing asset would render a broken image on paper with no error anywhere,
    which is exactly the failure a test should catch rather than a person.
    """
    from qsprofile import render
    from qsprofile.render import front_photo_uri
    cfg, problems = load(str(FX / "ddfortnite.csv"))
    html = render(cfg, {"game": "Test", "outputs": {}, "modes": {}, "inputs": {}},
                  validate(cfg, problems))
    assert "data:image/webp;base64," in html
    assert len(front_photo_uri()) > 20_000        # the real photo, not a stub
    for part in ("Left", "Center", "Right", "Side tube", "Joystick", "Status LEDs"):
        assert f"<b>{part}" in html


def test_card_photo_uses_the_lip_name_the_profile_chose():
    from qsprofile import render
    cfg, problems = load(str(FX / "ddfortnite.csv"))
    actions = {"game": "T", "outputs": {}, "modes": {}, "inputs": {"lip": "Chin switch"}}
    html = render(cfg, actions, validate(cfg, problems))
    assert "<b>Chin switch" in html and "<b>Lip button" not in html


# ---------------------------------------------------------------- Learn section (Stage 3)
def test_learn_section_examples_are_real_rows_in_the_fixtures():
    """web/src/learn/topics.ts teaches with rows taken out of the owner's own profiles.
    If a fixture changes, the lesson must not quietly become fiction — so the rows
    are asserted here rather than only in the front end's own tests."""
    fort, _ = load(str(FX / "ddfortnite.csv"))
    cod, _ = load(str(FX / "cod.csv"))

    def rows(cfg, mode_number):
        return {(m.output, m.function, tuple(m.inputs)) for m in cfg.modes[mode_number - 1].mappings}

    # "Aim down sights, hands-free": a latching puff on the left hole (modes 4-7)
    assert ("left_2", "toggle", ("mp_left_puff",)) in rows(fort, 4)
    # "Sprint that stays on": the same trick in Call of Duty, on two holes together
    assert ("left_3", "toggle", ("mp_left_center_sip",)) in rows(cod, 1)
    # "Auto-sprint by pushing the stick": pushing up also clicks the left stick
    assert ("left_3", "normal", ("up",)) in rows(fort, 6)
    # "Both stick clicks from one sip": two rows sharing one input
    assert ("left_3", "normal", ("mp_left_center_sip",)) in rows(fort, 1)
    assert ("right_3", "normal", ("mp_left_center_sip",)) in rows(fort, 1)
    # "A gentle puff that waits"
    assert ("right_3", "delay_on", ("mp_left_puff_soft",)) in rows(fort, 4)

    # and the three ways of aiming the first lesson describes
    assert [m.label for m in fort.modes][:5] == [
        "Left joy", "Left joy", "Right joy", "Left joy", "D-Pad",
    ]


def test_learn_section_only_teaches_functions_the_firmware_has():
    """The animations name output functions; every one must exist in the catalog."""
    import re
    from qsprofile.catalog import FUNCTIONS

    topics = (pathlib.Path(__file__).parent.parent / "web/src/learn/topics.ts").read_text()
    demos = re.findall(r"^\s*name: '([a-z_]+)',$", topics, re.MULTILINE)
    assert demos, "no function demos found; did topics.ts move?"
    unknown = [d for d in demos if d not in FUNCTIONS]
    assert not unknown, f"topics.ts teaches functions the firmware does not have: {unknown}"


# ---------------------------------------------------------------- prefs.csv (Stage 4)
def test_prefs_csv_round_trips_and_is_byte_stable(tmp_path):
    """`prefs.csv` uses the layout QMP writes: the firmware reads the file only when
    line 1 starts with `QuadStick`, then skips three lines before the settings. No mode
    blocks, because the file holds no profile."""
    from qsprofile import read_prefs_csv, write_prefs_csv

    prefs = {"volume": "40", "brightness": "7", "sip_puff_threshold": "55"}
    out = tmp_path / "prefs.csv"
    write_prefs_csv(prefs, str(out))

    raw = out.read_bytes()
    assert raw.startswith(b"QuadStick Configuration,Version 1.1\r\n"
                          b"Preferences,,,,\r\n"
                          b"prefs.csv,,,,\r\n"
                          b"Preference,Value,Units,Description,\r\n")
    assert b"Profile Name" not in raw
    assert raw.endswith(b"\r\n\r\n")                      # the add-on's trailing blank line
    for i, line in enumerate(raw.split(b"\r\n"), start=1):
        if line and i > 1:                                # line 1 is the only one without a comma
            assert line.endswith(b","), line             # every data line ends in a comma
            assert not line.endswith(b" ,")

    back, findings = read_prefs_csv(str(out))
    assert back == prefs
    assert not [f for f in findings if f[0] == "error"]

    again = tmp_path / "prefs2.csv"
    write_prefs_csv(back, str(again))
    assert again.read_bytes() == raw


def test_prefs_csv_keeps_a_key_it_does_not_recognise_but_says_so(tmp_path):
    from qsprofile import read_prefs_csv, write_prefs_csv

    out = tmp_path / "prefs.csv"
    write_prefs_csv({"volume": "40", "some_future_setting": "9"}, str(out))
    back, findings = read_prefs_csv(str(out))
    assert back["some_future_setting"] == "9"             # kept: the device may know it
    assert any("some_future_setting" in f[3] for f in findings)
    assert not any("volume" in f[3] for f in findings)


def test_reading_a_profile_as_prefs_is_reported_not_silently_accepted(tmp_path):
    """A profile .csv also carries a Preferences block, so the mistake is easy."""
    from qsprofile import read_prefs_csv

    prefs, findings = read_prefs_csv(str(FX / "cod.csv"))
    assert prefs                                          # the block is still read
    assert any("profile" in f[3] and "prefs.csv" in f[3] for f in findings)


def test_card_offers_printing_without_printing_the_offer(tmp_path):
    """The card is printed from the browser rather than through a PDF service, so it
    carries its own print button — and that button must not appear on the paper."""
    import json
    from qsprofile import render

    cfg, problems = load(str(FX / "ddfortnite.csv"))
    actions = json.loads((pathlib.Path(__file__).parent.parent / "actions/actions_fortnite.json").read_text())
    html = render(cfg, actions, validate(cfg, problems))

    assert "window.print()" in html
    assert "Print this card" in html
    # both the bar and the Checks page are marked screen-only
    assert 'class="printbar noprint"' in html
    assert html.count("noprint") >= 2
    # and the print stylesheet hides them, with !important so a sticky bar cannot
    # outrank it (which it did, until a browser check caught it)
    assert ".noprint{display:none!important}" in html.replace(" ", "")
    # A4, one page per mode, and the page break between them
    assert "size: A4" in html
    assert "page-break-after:always" in html
    assert html.count('<section class="page"') == len(cfg.modes) + 1   # + the front page
