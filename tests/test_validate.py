"""Rules in core/qsprofile/validate.py that the fixtures do not exercise.
Each test builds the smallest Config that trips one rule."""
import pathlib
import pytest
from qsprofile import Config, Mode, Mapping, load, validate, write_csv

FX = pathlib.Path(__file__).parent.parent / "fixtures"


def mode(number=1, rows=(), name="Mode", channel="usb"):
    m = Mode(number=number, name=name, label=name, channel=channel)
    for i, r in enumerate(rows):
        m.mappings.append(r if isinstance(r, Mapping) else Mapping(row=4 + i, **r))
    return m


def row(output="x", function="normal", params=(), inputs=("lip",), **kw):
    return dict(output=output, function=function, params=list(params), inputs=list(inputs), **kw)


def cfg(rows=None, filename="test.csv", preferences=None, modes=None):
    rows = rows if rows is not None else [row(output="increment_mode", inputs=["right_sip"])]
    return Config(name="Test", filename=filename, modes=modes or [mode(rows=rows)],
                  preferences=dict(preferences or {}))


def errors(findings):
    return [f for f in findings if f[0] == "error"]


def warnings(findings):
    return [f for f in findings if f[0] == "warning"]


# ---------------------------------------------------------------- hidden drive (C2 / C3)
def test_hidden_drive_rule_reads_the_file_not_a_column():
    """The Preferences block and a per-mode override row are what the device applies."""
    f = validate(cfg(preferences={"enable_DS3_emulation": "6"}), firmware=2373)
    hits = [x for x in warnings(f) if "hides the flash drive" in x[3]]
    assert hits and "firmware 2373" in hits[0][3]
    assert hits[0][1] is None and hits[0][2] is None

    override = Mapping(row=5, output="enable_DS3_emulation", function="", params=[], inputs=[],
                       kind="preference", value="7")
    c = cfg(rows=[row(output="increment_mode", inputs=["right_sip"]), override])
    f = validate(c)
    hits = [x for x in warnings(f) if "hides the flash drive" in x[3]]
    assert hits and hits[0][1] == 1 and hits[0][2] == 5 and "row 5" in hits[0][3]

    # firmware decides: 3 hides on both; 6 hides on 2373 only; 4 never
    assert any("hides the flash drive" in x[3] for x in validate(cfg(preferences={"enable_DS3_emulation": "3"}), firmware=1476))
    assert not any("hides the flash drive" in x[3] for x in validate(cfg(preferences={"enable_DS3_emulation": "6"}), firmware=1476))
    assert not any("hides the flash drive" in x[3] for x in validate(cfg(preferences={"enable_DS3_emulation": "4"})))
    # 2373 union set (decision D3): 1 and 3 warn too
    for v in ("1", "3", "5", "6", "7"):
        assert any("hides the flash drive" in x[3] for x in validate(cfg(preferences={"enable_DS3_emulation": v}))), v


def test_unknown_firmware_says_it_assumed_2373():
    """hidden_drive_modes() falls back to the 2373 set for a number it does not know;
    the message must say so rather than name that number as if it had a table for it."""
    from qsprofile import validate_preferences as vp
    for f in (validate(cfg(preferences={"enable_DS3_emulation": "6"}), firmware=9999),
              vp({"enable_DS3_emulation": "6"}, 9999, "global")):
        hits = [x for x in f if "hides the flash drive" in x[3]]
        assert hits, f
        msg = hits[0][3]
        assert "assuming firmware 2373" in msg and "9999 is not a firmware version" in msg
        assert "firmware 9999" not in msg and "on firmware" not in msg
    # a known or omitted firmware is still named plainly
    for f in (validate(cfg(preferences={"enable_DS3_emulation": "6"})),
              validate(cfg(preferences={"enable_DS3_emulation": "3"}), firmware=1476)):
        msg = [x for x in f if "hides the flash drive" in x[3]][0][3]
        assert "assuming" not in msg and " on firmware " in msg


def test_hidden_drive_in_default_csv_is_an_error():
    for name in ("default.csv", "prefs.csv", "DEFAULT.CSV"):
        f = validate(cfg(filename=name, preferences={"enable_DS3_emulation": "6"}))
        hits = [x for x in errors(f) if "hides the flash drive" in x[3]]
        assert hits, name
        assert "every boot" in hits[0][3]
    # a plain profile stays a warning, so export is not blocked
    f = validate(cfg(filename="game.csv", preferences={"enable_DS3_emulation": "6"}))
    assert not [x for x in errors(f) if "hides the flash drive" in x[3]]


# ---------------------------------------------------------------- function cells (C4)
@pytest.mark.parametrize("cell,fragment", [
    ("repeat five 2000", "whole numbers"),
    ("repeat 0 2000", "divides by zero"),
    ("repeat -1", "outside 0"),
    ("pulse 16384", "14-bit"),
    ("delay_on 0 500", "packed 0"),
    ("hold", "Unknown output function"),
    ("toggle 1", "at most 0 parameter"),
    ("repeat 2.5", "whole numbers"),
    ("repeat 05 2000", "written plainly"),
    ("repeat +5 2000", "written plainly"),
])
def test_function_param_rules_reject(cell, fragment):
    from qsprofile.catalog import parse_function, function_errors
    name, params, err = parse_function(cell)
    assert err and fragment in err, err
    assert function_errors(name, params) == [err]
    c = cfg(rows=[row(output="x", function=name, params=params, inputs=["lip"]),
                  row(output="increment_mode", inputs=["right_sip"])])
    hits = [f for f in errors(validate(c)) if fragment in f[3]]
    assert hits and hits[0][1] == 1 and hits[0][2] == 4, validate(c)


@pytest.mark.parametrize("cell", ["repeat 5 2000", "pulse 100 0", "greater_than 99", "normal", "toggle"])
def test_function_param_rules_accept(cell):
    from qsprofile.catalog import parse_function, function_errors
    name, params, err = parse_function(cell)
    assert err is None
    assert all(isinstance(p, int) for p in params)
    assert function_errors(name, params) == []
    c = cfg(rows=[row(output="x", function=name, params=params, inputs=["lip"]),
                  row(output="increment_mode", inputs=["right_sip"])])
    assert not errors(validate(c))


def test_parse_function_never_floats():
    from qsprofile.catalog import parse_function
    assert parse_function("repeat 2.5")[1] == ["2.5"]
    assert parse_function("repeat five 2000")[1] == ["five", 2000]
    assert parse_function("repeat 5 2000")[1] == [5, 2000]


@pytest.mark.parametrize("token", ["05", "+5", "00", "-0", "-05", "1_000", "٥"])
def test_parse_function_keeps_non_canonical_integers_as_strings(token):
    """int() would accept these and str() would write them back differently, so the
    file would change on re-export with no finding (decision D2 says keep the bytes)."""
    from qsprofile.catalog import parse_function
    name, params, err = parse_function(f"repeat {token} 2000")
    assert params == [token, 2000]
    assert err and "written plainly" in err


def test_parse_function_still_reads_plain_integers():
    from qsprofile.catalog import parse_function
    assert parse_function("repeat 0 2000")[1] == [0, 2000]
    assert parse_function("repeat -1")[1] == [-1]
    assert parse_function("pulse 16383 10")[1] == [16383, 10]


def test_non_canonical_integer_round_trips_byte_for_byte_and_is_an_error(tmp_path):
    src = tmp_path / "zero.csv"
    body = (b"QuadStick Configuration,Version 1.4,,Zero\r\n"
            b"Profile Name,,Left joy,\r\n"
            b"zero.csv,,Normal,\r\n"
            b"Output or Function,Function,usb,\r\n"
            b"x,repeat 05 2000,lip,\r\n"
            b"circle,pulse +5 2000,mp_left_sip,\r\n"
            b"increment_mode,normal,right_sip,\r\n"
            b"\r\n"
            b"Preferences,\r\n,,,,\r\nPreference,Value,Units,Description,\r\n\r\n")
    src.write_bytes(body)
    c, problems = load(str(src))
    assert c.modes[0].mappings[0].params == ["05", 2000]
    assert c.modes[0].mappings[1].params == ["+5", 2000]
    out = tmp_path / "out.csv"
    write_csv(c, str(out))
    assert out.read_bytes() == body                      # not rewritten as 'repeat 5 2000'
    f = validate(c, problems)
    assert [x for x in errors(f) if x[2] == 4 and "written plainly" in x[3] and "'05 2000'" in x[3]]
    assert [x for x in errors(f) if x[2] == 5 and "written plainly" in x[3] and "'+5 2000'" in x[3]]


def test_bad_function_cell_round_trips_byte_for_byte_and_is_an_error(tmp_path):
    src = tmp_path / "bad.csv"
    body = (b"QuadStick Configuration,Version 1.4,,Bad\r\n"
            b"Profile Name,,Left joy,\r\n"
            b"bad.csv,,Normal,\r\n"
            b"Output or Function,Function,usb,\r\n"
            b"x,repeat five 2000,lip,\r\n"
            b"circle,repeat 2.5,mp_left_sip,\r\n"
            b"increment_mode,normal,right_sip,\r\n"
            b"\r\n"
            b"Preferences,\r\n,,,,\r\nPreference,Value,Units,Description,\r\n\r\n")
    src.write_bytes(body)
    c, problems = load(str(src))
    assert c.modes[0].mappings[0].params == ["five", 2000]
    # the parser no longer reports it (no duplicate); validate() does
    assert not [p for p in problems if "five" in p[3]]
    out = tmp_path / "out.csv"
    write_csv(c, str(out))
    assert out.read_bytes() == body
    f = validate(c, problems)
    assert [x for x in errors(f) if x[2] == 4 and "whole numbers" in x[3]]
    assert [x for x in errors(f) if x[2] == 5 and "whole numbers" in x[3]]


def test_empty_function_is_an_info_not_an_error():
    c = cfg(rows=[row(output="x", function="", params=[], inputs=["lip"]),
                  row(output="increment_mode", inputs=["right_sip"])])
    f = validate(c)
    assert not errors(f)
    assert any(x[0] == "info" and "no function" in x[3] and x[2] == 4 for x in f)


# ---------------------------------------------------------------- filename (C5)
def test_filename_rule_uses_the_shared_helper():
    f = validate(cfg(filename="../evil.csv"))
    assert [x for x in errors(f) if x[2] == 2 and "A2" in x[3] and "/" in x[3]]
    f = validate(cfg(filename="x" * 28 + ".csv"))
    assert [x for x in errors(f) if "32 characters" in x[3]]
    f = validate(cfg(filename="Fortnite.csv"))
    assert not errors(f)
    assert any(x[0] == "info" and "fortnite.csv" in x[3] for x in f)


# ---------------------------------------------------------------- no CSV escaping (D4)
def test_label_that_forges_a_header_line_is_an_error():
    c = cfg(modes=[mode(name="Evil", rows=[row(output="increment_mode", inputs=["right_sip"])])])
    c.modes[0].label = "Left joy\r\nOutput or Function,Function,usb,"
    hits = [x for x in errors(validate(c)) if x[1] == 1 and x[2] == 1 and "C1" in x[3]]
    assert hits, validate(c)


def test_comma_in_a_preference_value_is_an_error():
    f = validate(cfg(preferences={"bluetooth_remote_address": "aa,bb"}))
    assert [x for x in errors(f) if "bluetooth_remote_address" in x[3] and "comma" in x[3]]


def test_non_ascii_mode_label_is_an_error():
    c = cfg()
    c.modes[0].label = "Gauche joystick é"
    assert [x for x in errors(validate(c)) if "non-ASCII" in x[3]]


def test_non_ascii_or_comma_in_mapping_cells_is_an_error():
    c = cfg(rows=[row(output="x", inputs=["lip"], comment="fine, comments are not exported"),
                  row(output="increment_mode", inputs=["right_sip"])])
    assert not errors(validate(c))
    c.modes[0].mappings[0].inputs = ["lip,mp_left_sip"]
    assert [x for x in errors(validate(c)) if x[2] == 4 and "comma" in x[3]]


def test_profile_name_with_a_comma_is_a_warning_and_a_line_break_an_error():
    c = cfg()
    c.name = "Call of Duty, Advanced"           # line 1 is unparsed past 'QuadStick'
    f = validate(c)
    assert [x for x in warnings(f) if "profile name" in x[3] and "comma" in x[3]]
    assert not errors(f)
    c.name = "Evil\r\nProfile Name,,X,"
    assert [x for x in errors(validate(c)) if "profile name" in x[3] and "line break" in x[3]]
    c.name = "Café"
    assert [x for x in errors(validate(c)) if "profile name" in x[3] and "non-ASCII" in x[3]]


# ------------------------------------------- name vs filename (the device loads the file)
@pytest.mark.parametrize("name, filename", [
    ("Call of Duty WWII", "cvcodww2.csv"),      # a prose label against a short device name
    ("Fortnite - Dad's build", "ddfortnite.csv"),
    ("cvcodww2 (copy)", "cvcodww2_copy.csv"),
    ("", "test.csv"),                           # a blank name is legal and round-trips
])
def test_a_name_that_does_not_match_its_filename_says_nothing(name, filename):
    """The firmware loads by filename and never reads line 1's title, so the name is
    free text for the owner. A mismatch warning was tried on 2026-09-15 and removed the
    same day: it fired on four of the six fixtures, which is how you know it was wrong.
    Nothing here may report on the name differing from the filename, at any severity."""
    c = cfg()
    c.name, c.filename = name, filename
    f = validate(c)
    assert not [x for x in f if "differ" in x[3] and "QuadStick this profile is" in x[3]], f
    assert not errors(f)


# ---------------------------------------------------------------- limits (off by one)
def test_keyword_limit_is_63_characters():
    from qsprofile.catalog import MAX_KEYWORD_CHARS
    ok = "kb_" + "a" * 60          # 63 chars
    c = cfg(rows=[row(output=ok, inputs=["lip"]), row(output="increment_mode", inputs=["right_sip"])])
    assert not [x for x in errors(validate(c)) if "characters" in x[3]]
    c.modes[0].mappings[0].output = ok + "a"       # 64
    assert [x for x in errors(validate(c)) if f"at most {MAX_KEYWORD_CHARS}" in x[3]]


def test_line_limit_is_1023_bytes():
    from qsprofile.catalog import MAX_LINE_BYTES
    inputs = ["lip"] * 7 + ["l" * 40]
    c = cfg(rows=[row(output="x", inputs=inputs), row(output="increment_mode", inputs=["right_sip"])])
    line = "x,normal ," + ",".join(inputs) + ",,"
    assert not [x for x in errors(validate(c)) if "bytes" in x[3]]
    c.modes[0].mappings[0].inputs = ["lip"] * 7 + ["l" * (MAX_LINE_BYTES - len(line) + 41)]
    assert [x for x in errors(validate(c)) if f"at most {MAX_LINE_BYTES}" in x[3]]


# ---------------------------------------------------------------- preferences
def test_profile_scope_preferences_are_validated():
    f = validate(cfg(preferences={"volume": "999", "mouse_speed": "1,2", "some_future": "9",
                                  "enable_DS3_emulation": "9", "enable_rumble": "2"}))
    msgs = [x[3] for x in errors(f)]
    assert any("Speaker volume" in m and "highest" in m for m in msgs)
    assert any("mouse_speed" in m and "comma" in m for m in msgs)
    assert any("enable_DS3_emulation" in m and "must be one of" in m for m in msgs)
    assert any("enable_rumble" in m and "highest the QuadStick accepts is 1" in m for m in msgs)
    assert any(x[0] == "info" and "some_future" in x[3] and "not a setting" in x[3] for x in f)


def test_validate_preferences_scopes():
    from qsprofile import validate_preferences as vp
    # global: a drive-hiding mode is an error, it applies at every boot
    f = vp({"enable_DS3_emulation": "6"}, 2373, "global")
    assert f and f[0][0] == "error" and "hides the flash drive" in f[0][3] and "firmware 2373" in f[0][3]
    assert not vp({"enable_DS3_emulation": "6"}, 1476, "global")
    # profile: the drive check lives in validate() (it needs the filename); here nothing
    assert not vp({"enable_DS3_emulation": "6"}, 2373, "profile")
    # mode: the firmware reads override values with atoi
    f = vp({"bluetooth_device_mode": "keyboard"}, 2373, "mode")
    assert [x for x in f if x[0] == "error" and "atoi" in x[3]]
    assert not vp({"bluetooth_device_mode": "3"}, 2373, "mode")
    f = vp({"digital_out_1": "1"}, 2373, "mode")
    assert [x for x in f if x[0] == "warning" and "ignores this here" in x[3]]
    assert not [x for x in vp({"mouse_speed": "120"}, 2373, "mode") if x[0] != "info"]
    with pytest.raises(ValueError):
        vp({}, 2373, "device")


@pytest.mark.parametrize("prefs,bad", [
    ({"sip_puff_threshold_soft": "40", "sip_puff_threshold": "41"}, "sip_puff_threshold"),
    ({"sip_puff_threshold": "70", "sip_puff_maximum": "70"}, "sip_puff_maximum"),
    ({"lip_position_minimum": "30", "lip_position_maximum": "33"}, "lip_position_maximum"),
    ({"joystick_D_Pad_inner": "80", "joystick_D_Pad_outer": "80"}, "joystick_D_Pad_outer"),
    ({"sip_threshold_soft": "50", "sip_threshold": "50"}, "sip_threshold"),
    ({"puff_threshold": "60", "puff_maximum": "60"}, "puff_maximum"),
])
def test_threshold_ordering_is_enforced(prefs, bad):
    from qsprofile import validate_preferences as vp
    f = vp(prefs, 2373, "global")
    assert [x for x in f if x[0] == "error" and bad in x[3] and "gap" in x[3]], f
    f = validate(cfg(preferences=prefs))
    assert [x for x in errors(f) if bad in x[3]]


def test_threshold_ordering_skips_unset_directional_values_and_good_gaps():
    from qsprofile import validate_preferences as vp
    assert not vp({"sip_threshold_soft": "0", "sip_threshold": "0", "sip_maximum": "0"}, 2373, "profile")
    assert not vp({"sip_puff_threshold_soft": "8", "sip_puff_threshold": "40", "sip_puff_maximum": "70"}, 2373, "profile")
    assert not vp({"sip_puff_threshold": "68", "sip_puff_maximum": "70"}, 2373, "profile")


def test_mode_override_rows_get_the_scope_rules_and_thresholds():
    ov = lambda r, k, v: Mapping(row=r, output=k, function="", params=[], inputs=[], kind="preference", value=v)
    c = cfg(rows=[row(output="increment_mode", inputs=["right_sip"]),
                  ov(5, "digital_out_1", "1"), ov(6, "mouse_speed", "fast"),
                  ov(7, "sip_puff_threshold", "70"), ov(8, "sip_puff_maximum", "70")])
    f = validate(c)
    assert [x for x in warnings(f) if x[2] == 5 and "ignores this here" in x[3]]
    assert [x for x in errors(f) if x[2] == 6 and "atoi" in x[3]]
    assert [x for x in errors(f) if x[2] == 8 and "sip_puff_maximum" in x[3] and "gap" in x[3]]


def test_new_2373_keywords_no_longer_block_export():
    c = cfg(rows=[row(output="xac_left_A", inputs=["mp_right_mode_sip"]),
                  row(output="kb_left_shift", inputs=["usb_1_button_16"]),
                  row(output="touch_up", inputs=["any_direction"]),
                  row(output="digital_out4_toggle", inputs=["constant"]),
                  row(output="increment_mode", inputs=["right_sip"])])
    assert not errors(validate(c))
    c.modes[0].mappings[1].output = "kb_leftshift"
    assert [x for x in errors(validate(c)) if "Unknown output 'kb_leftshift'" in x[3]]


# ---------------------------------------------------------------- firmware behaviours (Part 3)
def test_reset_quadstick_on_push_warns_about_the_bootloader():
    c = cfg(rows=[row(output="reset_quadstick", inputs=["push"]),
                  row(output="increment_mode", inputs=["right_sip"])])
    f = validate(c)
    assert [x for x in warnings(f) if x[2] == 4 and "bootloader" in x[3]]
    c.modes[0].mappings[0].inputs = ["lip"]
    assert not [x for x in warnings(validate(c)) if "bootloader" in x[3]]


def test_any_direction_with_square_dead_zone_is_stuck_on():
    rows = [row(output="x", inputs=["any_direction"]), row(output="increment_mode", inputs=["right_sip"])]
    assert not [x for x in warnings(validate(cfg(rows=rows))) if "stuck on" in x[3]]           # default shape 1
    f = validate(cfg(rows=rows, preferences={"joystick_dead_zone_shape": "0"}))
    assert [x for x in warnings(f) if x[2] == 4 and "stuck on" in x[3]]
    # a per-mode override row wins over the profile block
    ov = Mapping(row=6, output="joystick_dead_zone_shape", function="", params=[], inputs=[],
                 kind="preference", value="1")
    f = validate(cfg(rows=rows + [ov], preferences={"joystick_dead_zone_shape": "0"}))
    assert not [x for x in warnings(f) if "stuck on" in x[3]]


@pytest.mark.parametrize("mode_value", ["2", "3"])
def test_triggers_in_xbox_emulation_modes_are_an_axis(mode_value):
    rows = [row(output="left_2", inputs=["mp_left_puff"]), row(output="right_2", inputs=["mp_right_puff"]),
            row(output="increment_mode", inputs=["right_sip"])]
    f = validate(cfg(rows=rows, preferences={"enable_DS3_emulation": mode_value}))
    hits = [x for x in warnings(f) if "1 of 255" in x[3]]
    assert [x[2] for x in hits] == [4, 5]
    assert not [x for x in warnings(validate(cfg(rows=rows, preferences={"enable_DS3_emulation": "4"})))
                if "1 of 255" in x[3]]


# ---------------------------------------------------------------- C3 channel words (C6)
@pytest.mark.parametrize("channel", ["usb", "bluetooth", "both", "none"])
def test_every_firmware_channel_word_is_accepted_in_c3(channel):
    c = cfg(modes=[mode(rows=[row(output="increment_mode", inputs=["right_sip"])], channel=channel)])
    assert not [x for x in validate(c) if x[2] == 3 and "C3 is" in x[3]]


def test_unknown_channel_word_is_an_error():
    c = cfg(modes=[mode(rows=[row(output="increment_mode", inputs=["right_sip"])], channel="wifi")])
    hits = [x for x in errors(validate(c)) if x[1] == 1 and x[2] == 3 and "C3 is 'wifi'" in x[3]]
    assert hits and "usb, bluetooth, both, none" in hits[0][3]


def test_empty_channel_stays_a_warning_because_export_writes_usb():
    c = cfg(modes=[mode(rows=[row(output="increment_mode", inputs=["right_sip"])], channel="")])
    f = validate(c)
    assert not errors(f)
    hits = [x for x in warnings(f) if x[2] == 3 and "C3 is empty" in x[3]]
    assert hits and "usb" in hits[0][3]


@pytest.mark.parametrize("channel,fragment", [
    ("usb,x", "comma"), ("usb\r\nx", "line break"), ("usbé", "non-ASCII"),
])
def test_unsafe_text_in_channel_is_an_error_not_an_unknown_word(channel, fragment):
    """`channel="usb,x"` would export `Output or Function,Function,usb,x,` and shift the
    header's cells (D4); it is reachable only by building the model directly."""
    c = cfg(modes=[mode(rows=[row(output="increment_mode", inputs=["right_sip"])], channel=channel)])
    f = validate(c)
    c3 = [x for x in f if x[2] == 3 and x[3].startswith("C3")]
    assert len(c3) == 1 and c3[0][0] == "error" and fragment in c3[0][3], f


@pytest.mark.parametrize("channel", ["bluetooth", "none"])
def test_kb_and_mouse_outputs_off_usb_are_warned(channel):
    rows = [row(output="kb_a", inputs=["lip"]), row(output="mouse_left_button", inputs=["mp_left_sip"]),
            row(output="increment_mode", inputs=["right_sip"])]
    c = cfg(modes=[mode(rows=rows, channel=channel)])
    hits = [x for x in warnings(validate(c)) if "will not reach the cable" in x[3]]
    assert len(hits) == 1 and hits[0][1] == 1 and hits[0][2] == 4
    assert "rows 4, 5" in hits[0][3] and channel in hits[0][3]


@pytest.mark.parametrize("channel", ["usb", "both"])
def test_kb_and_mouse_outputs_on_usb_are_not_warned(channel):
    c = cfg(modes=[mode(rows=[row(output="kb_a", inputs=["lip"]),
                              row(output="increment_mode", inputs=["right_sip"])], channel=channel)])
    assert not [x for x in validate(c) if "reach the cable" in x[3]]


def test_gamepad_outputs_off_usb_are_not_warned():
    c = cfg(modes=[mode(rows=[row(output="cross", inputs=["lip"]),
                              row(output="increment_mode", inputs=["right_sip"])], channel="bluetooth")])
    assert not [x for x in validate(c) if "reach the cable" in x[3]]
