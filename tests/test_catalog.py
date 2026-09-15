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
