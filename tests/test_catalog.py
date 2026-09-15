"""The catalog is the single source of truth for keywords, limits and filenames."""
import pytest
from qsprofile import catalog as C


# ---------------------------------------------------------------- filenames (C5)
@pytest.mark.parametrize("name", ["ddfortnite.csv", "cod.csv", "a.csv", "my-game_2.csv",
                                  "x" * 27 + ".csv", "Fortnite.CSV"])
def test_device_filenames_are_accepted(name):
    assert C.check_csv_filename(name) is None


@pytest.mark.parametrize("name,fragment", [
    ("", "empty"),
    ("../evil.csv", "/"),
    ("/tmp/evil.csv", "/"),
    ("a\\b.csv", "\\"),
    ("c:x.csv", ":"),
    ("what?.csv", "?"),
    ("a,b.csv", "comma"),
    ("my game.csv", "whitespace"),
    (".hidden.csv", "dot"),
    ("x" * 28 + ".csv", "32 characters"),
    ("game.txt", "end in .csv"),
    ("gäme.csv", "ASCII"),
    ("game.csv.bak", "end in .csv"),
    ("a+b.csv", "cannot use"),
])
def test_device_filenames_are_refused_with_a_reason(name, fragment):
    msg = C.check_csv_filename(name)
    assert msg and fragment in msg, msg


def test_filename_regex_is_lowercase_and_bounded():
    assert C.CSV_FILENAME_RE.match("abc.csv")
    assert not C.CSV_FILENAME_RE.match("ABC.csv")          # callers lowercase first
    assert not C.CSV_FILENAME_RE.match("x" * 28 + ".csv")  # 31 chars total
    assert C.MAX_CSV_FILENAME_CHARS == 31


# ---------------------------------------------------------------- firmware 2373 keywords
def _qcm_inputs():
    """The 140 input keywords QCM's validation.json lists for firmware 2373, regenerated."""
    tubes = ["left", "center", "right", "left_center", "right_center", "left_right", "right_mode", "triple"]
    names = ["center"] + [f"mp_{t}_{a}{s}" for s in ("", "_soft") for t in tubes for a in ("sip", "puff")]
    names += ["right_sip", "right_puff", "right_sip_soft", "right_puff_soft", "lip",
              "left", "right", "up", "down", "any_direction"]
    names += C.JOY_ZONES + [f"{z}_inner" for z in C.JOY_ZONES] + ["constant"]
    for u in (1, 2):
        names += [f"usb_{u}_{d}" for d in C.JOY_DIRS]
    for u in (1, 2):
        names += [f"usb_{u}_{z}" for z in C.JOY_ZONES] + [f"usb_{u}_{z}_inner" for z in C.JOY_ZONES]
    for u in (1, 2):
        names += [f"usb_{u}_button_{n}" for n in range(1, 17)]
    names += [f"digital_in_{n}" for n in range(1, 9)]
    assert len(names) == 140
    return names


def test_every_firmware_2373_input_classifies():
    unknown = [n for n in _qcm_inputs() if C.classify_input(n) is None]
    assert not unknown, unknown
    assert C.classify_input("usb_1_button_17") is None
    assert C.classify_input("mp_right_mode_puff")["kind"] == "mouthpiece"
    assert C.classify_input("any_direction")["kind"] == "joystick"
    assert C.classify_input("constant")["label"] == "Always on"
    assert C.classify_input("none")["kind"] == "none"


def test_every_firmware_2373_output_is_in_the_catalog():
    xac = ["xac_left_A", "xac_left_B", "xac_left_LB", "xac_left_LS", "xac_left_menu", "xac_left_view",
           "xac_left_up", "xac_left_down", "xac_right_X", "xac_right_Y", "xac_right_RB", "xac_right_RS",
           "xac_right_menu", "xac_right_view", "xac_right_up", "xac_right_down"]
    extra = xac + ["touch_up", "touch_down", "touch_left", "touch_right", "none",
                   "digital_out3_on", "digital_out3_off", "digital_out3_toggle",
                   "digital_out4_on", "digital_out4_off", "digital_out4_toggle",
                   "digital_out_1", "digital_out_2", "digital_out_3", "digital_out_4"]
    missing = [n for n in extra if C.output_label(n) is None]
    assert not missing, missing
    assert len(C.KEYBOARD) == 215 and len(C.INFRARED) == 27       # QCM validation.json
    for n in ("kb_a", "kb_left_shift", "kb_keypad_000", "kb_right_gui", "ir_tv_on_off", "ir_aux4"):
        assert n in C.OUTPUTS, n
    assert C.output_group("kb_a") == "keyboard" and C.output_group("ir_play") == "ir"
    # exact match: near misses are not keys, and the firmware would silently skip them
    for n in ("kb_leftshift", "kb_shift", "kb_ctrl", "kb_up", "ir_power"):
        assert C.output_label(n) is None, n


def test_capture_is_the_xbox_name_for_touch():
    assert C.canonical_output("capture", "xbox") == "touch"
    assert C.display_output("touch", "xbox") == "capture"
    assert "touch" not in C.NO_XBOX_EQUIVALENT
    assert C.NO_XBOX_EQUIVALENT == {"touch_up", "touch_down", "touch_left", "touch_right"}


def test_limits_are_the_firmware_caps_not_the_buffer_sizes():
    assert C.MAX_KEYWORD_CHARS == 63
    assert C.MAX_LINE_BYTES == 1023
    assert C.MAX_FUNCTION_PARAM == 16383


@pytest.mark.parametrize("value,fragment", [
    ("a,b", "comma"), ("a\nb", "line break"), ("a\rb", "line break"), ("gäme", "non-ASCII"),
])
def test_unsafe_text_names_the_problem(value, fragment):
    assert fragment in C.unsafe_text(value)


def test_unsafe_text_accepts_plain_ascii():
    assert C.unsafe_text("Left joy") is None
    assert C.unsafe_text("") is None
    assert C.unsafe_text(None) is None


def test_relay_outputs_are_outputs_first_and_named_alike_on_both_consoles():
    """digital_out_1..4 are both an output keyword and a preference key. The firmware
    checks outputs first, so the catalog must list them as outputs (family DIGITAL_OUT)
    or the parser would read `digital_out_1,,1,` in a mode as an override."""
    for n in (1, 2, 3, 4):
        name = f"digital_out_{n}"
        assert name in C.DIGITAL_OUT and name in C.PREFERENCES
        assert C.output_label(name) == f"Relay {n}"
        assert C.canonical_output(name, "xbox") == name and C.display_output(name, "xbox") == name
        assert C.output_group(name) == "other"
        assert name not in C.NO_XBOX_EQUIVALENT
    assert len(C.DIGITAL_OUT) == 16


# ---------------------------------------------------------------- firmware fallback
def test_firmware_phrase_matches_the_set_hidden_drive_modes_used():
    assert C.hidden_drive_modes(9999) == C.HIDDEN_DRIVE_MODES[C.DEFAULT_FIRMWARE]
    assert C.hidden_drive_modes(None) == C.HIDDEN_DRIVE_MODES[C.DEFAULT_FIRMWARE]
    assert C.firmware_phrase(2373) == " on firmware 2373"
    assert C.firmware_phrase(1476) == " on firmware 1476"
    assert C.firmware_phrase(None) == f" on firmware {C.DEFAULT_FIRMWARE}"
    phrase = C.firmware_phrase(9999)
    assert phrase.startswith(", assuming firmware 2373") and "9999" in phrase


# ---------------------------------------------------------------- derived filenames (W2)
def test_a_derived_filename_keeps_a_short_stem_as_it_is():
    assert C.derived_csv_filename("ddfortnite.csv", "copy") == "ddfortnite_copy.csv"
    assert C.derived_csv_filename("cod.csv", "ps") == "cod_ps.csv"
    assert C.derived_csv_filename("cod.csv", "xbox") == "cod_xbox.csv"


@pytest.mark.parametrize("suffix", ["copy", "ps", "xbox"])
def test_a_derived_filename_never_exceeds_what_the_device_loads(suffix):
    """The stem is cut, not the suffix: the server invents these names and the user
    never gets a chance to shorten them."""
    name = C.derived_csv_filename("a" * 27 + ".csv", suffix)
    assert len(name) <= C.MAX_CSV_FILENAME_CHARS
    assert name.endswith(f"_{suffix}.csv")
    assert C.check_csv_filename(name) is None


def test_a_derived_filename_is_lowercased_and_never_ends_in_a_separator():
    assert C.derived_csv_filename("MyGame.CSV", "copy") == "mygame_copy.csv"
    # the cut must not leave `stem__copy.csv` or `stem-_copy.csv`
    assert C.derived_csv_filename("a" * 20 + "_____.csv", "copy") == "a" * 20 + "_copy.csv"
    assert C.derived_csv_filename(".csv", "copy") == "profile_copy.csv"
    assert C.derived_csv_filename("", "copy") == "profile_copy.csv"


# ------------------------------------------------- name -> filename (the shared rule)
def test_a_name_becomes_the_filename_the_device_will_show():
    assert C.csv_filename_for_name("Call of Duty") == "call_of_duty.csv"
    assert C.csv_filename_for_name("MyGame") == "mygame.csv"
    # a name that is already a filename stem comes back unchanged
    assert C.csv_filename_for_name("ddfortnite") == "ddfortnite.csv"


def test_the_name_rule_keeps_underscores_and_dashes():
    """check_csv_filename permits _ and -, so the rule must keep them: an earlier
    frontend slug stripped both and invented a different name for the same profile."""
    assert C.csv_filename_for_name("cvcodww2_copy") == "cvcodww2_copy.csv"
    assert C.csv_filename_for_name("My_Game-2") == "my_game-2.csv"
    assert C.csv_filename_for_name("cod_ps") == "cod_ps.csv"


def test_the_name_rule_collapses_anything_else_to_one_underscore():
    assert C.csv_filename_for_name("Call of  Duty: WWII!") == "call_of_duty_wwii.csv"
    assert C.csv_filename_for_name("a / b \\ c") == "a_b_c.csv"
    assert C.csv_filename_for_name("  spaced  ") == "spaced.csv"
    assert C.csv_filename_for_name("--dash--") == "dash.csv"
    assert C.csv_filename_for_name("...dots...") == "dots.csv"


def test_a_long_name_is_cut_to_what_the_device_loads():
    name = C.csv_filename_for_name("Call of Duty Advanced Warfare XBox One Remastered")
    assert len(name) <= C.MAX_CSV_FILENAME_CHARS
    assert C.check_csv_filename(name) is None
    # the cut never leaves a trailing separator
    assert C.csv_filename_for_name("a" * 20 + " " * 3 + "b" * 20) == "a" * 20 + "_" + "b" * 6 + ".csv"
    assert not C.csv_filename_for_name("a" * 26 + " tail").rsplit(".", 1)[0].endswith("_")


def test_a_name_with_nothing_usable_falls_back_to_profile():
    for empty in ("", None, "   ", "!!!", "...", "___", "😀"):
        assert C.csv_filename_for_name(empty) == "profile.csv", empty


@pytest.mark.parametrize("name", [
    "Call of Duty", "ddfortnite", "My_Game-2", "a" * 60, "!!!", "", "Grand Theft Auto V",
    "x,y", "ü ber", "Mode 1 / Mode 2", "-" * 40, "9", "CAPS LOCK NAME",
])
def test_every_derived_filename_is_one_the_device_loads(name):
    assert C.check_csv_filename(C.csv_filename_for_name(name)) is None


# ---------------------------------------------------------------- firmware (W19)
@pytest.mark.parametrize("fw", C.FIRMWARE_VERSIONS)
def test_a_known_firmware_has_no_complaint(fw):
    assert C.check_firmware(fw) is None


def test_an_unknown_firmware_says_which_versions_are_known():
    msg = C.check_firmware(9999)
    assert "Unknown firmware 9999" in msg
    assert "2373" in msg and "1476" in msg
    assert C.check_firmware(None) is not None
