"""The qstest profile (core/qsprofile/tester.py): the device file and the page's
spec come from one table, the file is the one already loaded on a QuadStick, and
every keyword in it is in the catalog."""
import pathlib
from qsprofile import catalog as C, load, tester, validate, write_csv

FX = pathlib.Path(__file__).parent.parent / "fixtures"


def test_the_generated_profile_is_the_device_file(tmp_path):
    """fixtures/qstest.csv is the dronecontrol generator's output, the file the
    tester was built and measured against. write_csv ends every file with the
    add-on's trailing blank line; that is the only byte that differs."""
    out = tmp_path / "qstest.csv"
    write_csv(tester.config(), str(out))
    assert out.read_bytes() == (FX / "qstest.csv").read_bytes() + b"\r\n"


def test_the_device_file_parses_back_to_the_same_modes():
    cfg, _ = load(str(FX / "qstest.csv"))
    ours = tester.config()
    assert cfg.filename == "qstest.csv" and cfg.name == "qstest"
    assert [(m.number, m.label, m.channel) for m in cfg.modes] == \
           [(m.number, m.label, m.channel) for m in ours.modes]
    for a, b in zip(cfg.modes, ours.modes):
        assert [(m.output, m.function, m.inputs) for m in a.mappings] == \
               [(m.output, m.function, m.inputs) for m in b.mappings]


def test_the_profile_passes_every_check():
    assert validate(tester.config()) == []


def test_every_keyword_is_in_the_catalog():
    for o in list(tester.BITS) + list(tester.HAT):
        assert o in C.OUTPUTS, o
    for i in tester.INPUTS:
        assert C.classify_input(i)["kind"] in ("mouthpiece", "side", "lip"), i


def test_the_spec_matches_the_profile_row_for_row():
    """Every button the page decodes is the button the profile drives with that
    input, in that mode, and the hat the page reads is the d-pad that mode holds."""
    cfg, sp = tester.config(), tester.spec()
    assert [m["n"] for m in sp["modes"]] == [m.number for m in cfg.modes]
    for mode, sm in zip(cfg.modes, sp["modes"]):
        rows = {m.output: m.inputs[0] for m in mode.mappings}
        held = [o for o, i in rows.items() if i == "constant"]
        assert held == [o for o, h in tester.HAT.items() if h == sm["hat"]]
        for e in sm["map"]:
            assert rows[e["out"]] == e["input"]
            assert (e["byte"], e["mask"]) == tester.BITS[e["out"]]
            assert e["input"] in sp["inputs"]


def test_each_mode_holds_a_different_marker_and_no_released_hat():
    hats = [m["hat"] for m in tester.spec()["modes"]]
    assert len(set(hats)) == len(hats)
    assert 15 not in hats and all(0 <= h <= 7 for h in hats)


def test_no_mode_drives_one_button_from_two_inputs():
    for m in tester.spec()["modes"]:
        bits = [(e["byte"], e["mask"]) for e in m["map"]]
        assert len(bits) == len(set(bits)), m["n"]


def test_the_web_tests_use_the_current_spec():
    """web/src/test/tester-spec.json is what the page's tests decode against. If this
    fails, regenerate it: python -c "import json; from qsprofile import tester;
    print(json.dumps(tester.spec(), indent=1))" > web/src/test/tester-spec.json"""
    import json
    path = pathlib.Path(__file__).parent.parent / "web" / "src" / "test" / "tester-spec.json"
    assert json.loads(path.read_text()) == tester.spec()
