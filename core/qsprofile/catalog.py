"""Canonical QuadStick vocabulary: inputs, outputs, output functions.

Sources: QuadStick user manual (dropdown lists), the real ddfortnite.xlsx
fixture (which adds `touch`), and QuadStick Config Manager's validation.json for
firmware 2373 (the kb_* / ir_* lists in keywords/, the XAC outputs and the inputs
the manual's dropdowns omit). Everything here is data so it can be moved into
Postgres later without changing the parser or validator.
"""
import re
from .preferences import PREFERENCES, MODE_OVERRIDABLE, CATEGORIES as PREFERENCE_CATEGORIES

# ---------------------------------------------------------------- inputs
TUBES = {
    "left": "Left", "center": "Center", "right": "Right",
    "left_center": "Left + Center", "right_center": "Right + Center",
    "left_right": "Left + Right", "triple": "All three",
    # firmware 2373 also parses mp_right_mode_*: the right hole together with the
    # side (mode) tube. Not in the manual's dropdowns and not a card grid column.
    "right_mode": "Right + Side tube",
}
TUBE_ORDER = ["left", "left_center", "center", "right_center", "right", "left_right", "triple"]

_MP_RE = re.compile(r"^mp_(left_center|right_center|left_right|right_mode|triple|left|center|right)_(sip|puff)(_soft)?$")
_SIDE_RE = re.compile(r"^right_(sip|puff)(_soft)?$")
_LIP_RE = re.compile(r"^lip(_soft)?$")
JOY_DIRS = ["up", "down", "left", "right"]
JOY_ZONES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_JOY_RE = re.compile(r"^(up|down|left|right|N|NE|E|SE|S|SW|W|NW)(_inner)?$")
_DIG_RE = re.compile(r"^digital_in_[1-8]$")
# Which physical jack each switch input lives on (QuadStick manual, back panel):
DIGITAL_JACKS = {1: "bottom 'In' jack", 2: "bottom 'In' jack",
                 3: "USB-A jack", 4: "USB-A jack",
                 5: "Lip button jack", 6: "Lip button jack",
                 7: "top 'In 7-8' jack", 8: "top 'In 7-8' jack"}
_USB_RE = re.compile(r"^usb_[12]_(up|down|left|right|N|NE|E|SE|S|SW|W|NW|button_(1[0-6]|[1-9]))(_inner)?$")
# Inputs that are not a sensor: always on, or an explicit "nothing" placeholder.
SPECIAL_INPUTS = {"constant": "Always on", "none": "No input"}
# Older input names the firmware (2373) still parses; accepted with a warning.
LEGACY_INPUTS = {
    "push": "Push on the joystick (older name)",
    "right_sip_long": "Side tube long sip (older name)",
    "right_puff_long": "Side tube long puff (older name)",
    "bluetooth_status": "Bluetooth connected (older name)",
}

# ------------------------------------------------ firmware and its hard limits
FIRMWARE_VERSIONS = (2373, 1476)
DEFAULT_FIRMWARE = 2373
MAX_MODES = 16
MAX_ROWS_PER_MODE = 128
MAX_KEYWORD_CHARS = 63      # next_word() returns NULL at 64 and the row loses every later field
MAX_LINE_BYTES = 1023       # f_gets keeps len-1; a longer line misframes the rest of the file
MAX_PREFERENCE_ROWS = {2373: 61, 1476: 50}
MAX_FUNCTION_PARAM = 16383      # the firmware packs each parameter into a 14-bit field
# Profile filenames: `char files[NUM_FILES][32]` with an unterminated strncpy on 2373, so
# 31 characters including .csv is the most that loads; the device lowercases every
# name; FAT forbids / \ : * ? " < > | and a comma would split the A2 cell.
MAX_CSV_FILENAME_CHARS = 31
CSV_FILENAME_RE = re.compile(r"^[a-z0-9_\-.]{1,27}\.csv$")
_FILENAME_FORBIDDEN = set('/\\:*?"<>|,')


def check_csv_filename(name):
    """None when the QuadStick will load a profile called `name`, else a plain
    sentence saying why not. Mixed case is accepted (the device lowercases names);
    callers that want to say what the device will call it compare with .lower()."""
    s = "" if name is None else str(name)
    if not s:
        return "the filename is empty; it must end in .csv"
    if not s.isascii():
        return f"'{s}' has non-ASCII characters; the QuadStick reads plain ASCII names"
    if any(ch.isspace() for ch in s):
        return f"'{s}' contains whitespace; use _ or - between words"
    bad = sorted(set(s) & _FILENAME_FORBIDDEN)
    if bad:
        return f"'{s}' contains {' '.join(bad)}; a filename may not contain / \\ : * ? \" < > | or a comma"
    if s.startswith("."):
        return f"'{s}' starts with a dot; the QuadStick deletes dot-files when it boots"
    if len(s) > MAX_CSV_FILENAME_CHARS:
        return (f"'{s}' is {len(s)} characters; the QuadStick stores at most "
                f"{MAX_CSV_FILENAME_CHARS} including .csv, and a longer name never loads")
    low = s.lower()
    if not low.endswith(".csv"):
        return f"'{s}' must end in .csv"
    if not CSV_FILENAME_RE.match(low):
        return f"'{s}' has characters the QuadStick cannot use; use letters, digits, _ - and ."
    return None
# enable_DS3_emulation values that hide the flash drive (a mistake then needs the
# side-tube recovery procedure). 2373: union of QCM's code ({1, 3, 5, 6, 7}, from the
# firmware USB descriptors) and its FORMAT.md ({5, 6, 7}); modes 1 and 3 are unverified
# on the owner's device. 1476 per the older manual.
HIDDEN_DRIVE_MODES = {2373: {1, 3, 5, 6, 7}, 1476: {3, 5, 7}}
EMULATION_MODES = {
    0: "QuadStick native (composite HID: PC, Mac, PS3, Brook adapters)",
    1: "DualShock 3", 2: "x360ce", 3: "Xbox 360", 4: "DualShock 4 (PS4 / PS5 via adapter)",
    5: "Nintendo Switch", 6: "DualShock 4, no USB drive", 7: "DualShock 4 wireless passthrough",
}


def hidden_drive_modes(firmware):
    """Which emulation modes hide the flash drive depends on the firmware, so this
    cannot be a constant. Unknown or missing firmware falls back to DEFAULT_FIRMWARE;
    firmware_phrase() is how a finding says which set it used."""
    fw = firmware or DEFAULT_FIRMWARE
    return HIDDEN_DRIVE_MODES.get(fw, HIDDEN_DRIVE_MODES[DEFAULT_FIRMWARE])


def firmware_phrase(firmware):
    """How a drive-hiding finding names the firmware whose set it used, to follow
    'hides the flash drive': ' on firmware 2373' when the version is known (or not
    given), ', assuming firmware 2373 (...)' when hidden_drive_modes() fell back for
    a number this app does not know, so the message never presents that number as
    one it has a table for."""
    fw = firmware or DEFAULT_FIRMWARE
    if fw in HIDDEN_DRIVE_MODES:
        return f" on firmware {fw}"
    return (f", assuming firmware {DEFAULT_FIRMWARE} ({fw} is not a firmware version "
            f"this app knows)")


def classify_input(name):
    """Return a dict describing an input name, or None if it is not valid."""
    if not name:
        return None
    if name in LEGACY_INPUTS:
        return {"kind": "legacy", "label": LEGACY_INPUTS[name]}
    m = _MP_RE.match(name)
    if m:
        tube, act, soft = m.groups()
        return {"kind": "mouthpiece", "tube": tube, "action": act,
                "strength": "soft" if soft else "hard",
                "label": f"{TUBES[tube]} {'soft ' if soft else ''}{act}"}
    m = _SIDE_RE.match(name)
    if m:
        act, soft = m.groups()
        return {"kind": "side", "tube": "side", "action": act,
                "strength": "soft" if soft else "hard",
                "label": f"Side tube {'soft ' if soft else ''}{act}"}
    m = _LIP_RE.match(name)
    if m:
        return {"kind": "lip", "strength": "soft" if m.group(1) else "hard",
                "label": "Lip button" + (" (soft)" if m.group(1) else "")}
    m = _JOY_RE.match(name)
    if m:
        d, inner = m.groups()
        return {"kind": "joystick", "dir": d, "ring": "inner" if inner else "outer",
                "label": f"Joystick {d}" + (" (inner)" if inner else "")}
    if _DIG_RE.match(name):
        n = int(name[-1])
        return {"kind": "digital", "number": n, "jack": DIGITAL_JACKS[n],
                "label": f"Switch input {n}"}
    if _USB_RE.match(name):
        return {"kind": "usb", "label": name.replace("_", " ")}
    if name == "center":
        return {"kind": "joystick", "dir": "center", "ring": "center", "label": "Joystick centred"}
    if name == "any_direction":
        return {"kind": "joystick", "dir": "any", "ring": "outer", "label": "Joystick any direction"}
    if name in SPECIAL_INPUTS:
        return {"kind": name, "label": SPECIAL_INPUTS[name]}
    return None


def all_mouthpiece_inputs():
    for tube in TUBE_ORDER:
        for act in ("sip", "puff"):
            for soft in ("", "_soft"):
                yield f"mp_{tube}_{act}{soft}"

# ---------------------------------------------------------------- outputs
PS_BUTTONS = {
    "x": "✕", "circle": "○", "square": "□", "triangle": "△",
    "left_1": "L1", "left_2": "L2", "left_3": "L3",
    "right_1": "R1", "right_2": "R2", "right_3": "R3",
    "select": "Share", "start": "Options", "ps3": "PS", "touch": "Touchpad",
}
DPAD = {f"dpad_{z}": f"D-pad {z}" for z in JOY_ZONES}
STICKS = {f"{s}_joy_{d}": f"{'Left' if s == 'left' else 'Right'} stick {d}"
          for s in ("left", "right") for d in JOY_DIRS}
SYSTEM = {
    "increment_mode": "Next mode", "decrement_mode": "Previous mode",
    "load_file": "Choose profile file", "reset_quadstick": "Reset QuadStick",
    "ps4_authentication": "Re-authenticate USB",
    "brightness_up": "LEDs brighter", "brightness_down": "LEDs dimmer",
    "volume_up": "Volume up", "volume_down": "Volume down",
}
MOUSE = {f"mouse_{k}": v for k, v in {
    "left": "Mouse left", "right": "Mouse right", "up": "Mouse up", "down": "Mouse down",
    "wheel_up": "Wheel up", "wheel_down": "Wheel down", "pan_left": "Pan left",
    "pan_right": "Pan right", "left_button": "Left click", "right_button": "Right click",
    "middle_button": "Middle click", "back": "Mouse back", "forward": "Mouse forward"}.items()}
MOTION = {f"acceleration_{a}": f"Accel {a}" for a in
          ("x_right", "x_left", "y_fore", "y_aft", "z_up", "z_down")}
MOTION.update({f"gyroscope_{a}_{r}": f"Gyro {a} {r}" for a in "xyz" for r in ("cw", "ccw")})
TOUCHPAD = {f"touch_{d}": f"Touchpad swipe {d}" for d in JOY_DIRS}
# Xbox Adaptive Controller outputs (firmware 2373): the two XAC "sides".
XAC = {f"xac_{side}_{b}": f"XAC {side} {b}" for side, btns in
       (("left", ("A", "B", "LB", "LS", "menu", "view", "up", "down")),
        ("right", ("X", "Y", "RB", "RS", "menu", "view", "up", "down"))) for b in btns}
# The relay outputs. `digital_out_N` (the bare name, also a preference key) follows the
# input like any button; the firmware matches column A against its output keywords
# before its preference table, so in a mode block it is always an output row. The
# names are the same on PlayStation and Xbox.
DIGITAL_OUT = {f"digital_out_{n}": f"Relay {n}" for n in (1, 2, 3, 4)}
DIGITAL_OUT.update({f"digital_out{n}_{s}": f"Relay {n} {s}" for n in (1, 2, 3, 4) for s in ("on", "off", "toggle")})


def _keywords(fname):
    """One keyword per line; '#' lines are attribution. Shipped as package data and
    read through importlib.resources so an installed, editable or PyInstaller-frozen
    package all find it."""
    from importlib.resources import files
    text = files("qsprofile").joinpath("keywords", fname).read_text(encoding="ascii")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


# The full kb_* and ir_* lists (keywords/*.txt, from QCM's validation.json). The
# firmware matches names exactly, so membership is the check; the two regexes below
# describe only the family shape and are kept for api.catalog_seed until wave 2.
KEYBOARD = {n: "Key " + n[3:].replace("_", " ") for n in _keywords("kb_outputs.txt")}
INFRARED = {n: "IR " + n[3:].replace("_", " ") for n in _keywords("ir_outputs.txt")}
_KB_RE = re.compile(r"^kb_[a-z0-9_]+$")
_IR_RE = re.compile(r"^ir_[a-z0-9_]+$")

# Xbox naming set (A3 header 'XBox Outputs'). The QuadStick treats these as the
# same underlying functions as the PlayStation names; only the label differs.
# Internally everything is stored under the PlayStation name (canonical).
XBOX_TO_PS = {
    "A": "x", "B": "circle", "X": "square", "Y": "triangle",
    "left_bumper": "left_1", "left_trigger": "left_2", "left_stick": "left_3",
    "right_bumper": "right_1", "right_trigger": "right_2", "right_stick": "right_3",
    "back": "select", "guide": "ps3", "start": "start",
    "capture": "touch",           # the firmware's Xbox name for the touchpad press
}
PS_TO_XBOX = {v: k for k, v in XBOX_TO_PS.items()}
XBOX_GLYPH = {"x": "A", "circle": "B", "square": "X", "triangle": "Y",
              "left_1": "LB", "left_2": "LT", "left_3": "LS",
              "right_1": "RB", "right_2": "RT", "right_3": "RS",
              "select": "View", "start": "Menu", "ps3": "Xbox", "touch": "Share"}
# PlayStation-only outputs: the Xbox keyword table (QCM validation.json,
# outputs_xbox) has no touchpad swipes. `touch` itself is `capture` on Xbox.
NO_XBOX_EQUIVALENT = set(TOUCHPAD)
LEGACY = {"gyroscope_cw": "Gyro cw", "gyroscope_ccw": "Gyro ccw"}   # older firmware names
MOTION.update(LEGACY)

OUTPUTS = {**PS_BUTTONS, **DPAD, **STICKS, **SYSTEM, **MOUSE, **MOTION, **TOUCHPAD, **XAC,
           **DIGITAL_OUT, **KEYBOARD, **INFRARED, "none": "No output"}


def canonical_output(name, console):
    """Map an output as written in a sheet to the canonical (PlayStation) name."""
    if console == "xbox" and name in XBOX_TO_PS:
        return XBOX_TO_PS[name]
    return name


def display_output(name, console):
    """Canonical name -> the name the sheet should use for the given console."""
    if console == "xbox":
        return PS_TO_XBOX.get(name, name)
    return name
MODE_CHANGE_OUTPUTS = {"increment_mode", "decrement_mode", "load_file"}


def output_label(name):
    """Friendly label, or None when the firmware has no such output (exact match:
    kb_leftshift is not a key, kb_left_shift is)."""
    return OUTPUTS.get(name)


def output_group(name):
    if name in PS_BUTTONS: return "button"
    if name in DPAD: return "dpad"
    if name in STICKS: return "stick"
    if name in SYSTEM: return "system"
    if name in KEYBOARD: return "keyboard"
    if name in INFRARED: return "ir"
    return "other"


def unsafe_text(value):
    """Why `value` cannot go into the device CSV unchanged, or None. write_csv
    never quotes or escapes (the firmware does not unquote) and writes ASCII, so a
    comma shifts the cells, a line break forges a new line and non-ASCII would
    silently become '?'. Decision D4: reject at validation and at the API edge."""
    s = "" if value is None else str(value)
    if "," in s:
        return "contains a comma, which the QuadStick reads as the next cell"
    if "\r" in s or "\n" in s:
        return "contains a line break, which the QuadStick reads as a new line"
    if not s.isascii():
        return "contains non-ASCII characters; the device file is plain ASCII"
    return None

# ------------------------------------------------------- output functions
# name -> (max params, plain-English description)
FUNCTIONS = {
    "normal": (0, "on while the input is active"),
    "toggle": (0, "one action turns it on, the next turns it off"),
    "repeat": (2, "auto-fires while held"),
    "pulse": (2, "one short press per action"),
    "duty": (2, "on-time scales with how hard you sip or puff"),
    "greater_than": (2, "on above a pressure threshold"),
    "less_than": (1, "on below a pressure threshold"),
    "force_off": (1, "forces the output off"),
    "delayed_latch": (1, "hold to latch, tap for momentary"),
    "delay_off": (1, "stays on briefly after you release"),
    "delay_on": (2, "starts after a short delay"),
    "tap": (2, "short tap presses, long hold does nothing"),
    "increment_value": (2, "steps the value up"),
    "decrement_value": (2, "steps the value down"),
}


# A parameter written the one way str(int) writes it back: no '+', no leading zero.
# '+5' and '05' would re-export as '5' and change the file behind the owner's back.
_INT_RE = re.compile(r"^(0|-?[1-9]\d*)$")


def parse_function(cell):
    """'repeat 5 2000' -> ('repeat', [5, 2000], error_or_None).

    A token becomes an int only when it is a canonically written one; anything
    else ('five', '2.5', '+5', '05') is kept verbatim so the file round-trips byte
    for byte (decision D2), and function_errors() reports it. Never float(): the
    firmware reads parameters with atoi."""
    parts = str(cell).strip().split()
    if not parts:
        return None, [], "Function cell is empty"
    name = parts[0]
    params = [int(t) if _INT_RE.match(t) else t for t in parts[1:]]
    errs = function_errors(name, params)
    return name, params, (errs[0] if errs else None)


def function_errors(name, params):
    """Why the firmware would misread this function cell; first failing rule wins,
    so the list is empty or has one message."""
    if name not in FUNCTIONS:
        return [f"Unknown output function '{name}'"]
    max_p, _ = FUNCTIONS[name]
    params = list(params or [])
    if len(params) > max_p:
        return [f"'{name}' takes at most {max_p} parameter(s), got {len(params)}"]
    shown = " ".join(str(p) for p in params)
    if any(isinstance(p, bool) or not isinstance(p, int) for p in params):
        return [f"Parameters for '{name}' must be whole numbers written plainly (no +, no leading zero), "
                f"got '{shown}' (the firmware reads them with atoi)"]
    for p in params:
        if p < 0 or p > MAX_FUNCTION_PARAM:
            return [f"'{name} {shown}': parameter {p} is outside 0–{MAX_FUNCTION_PARAM} (14-bit field)"]
    if name == "repeat" and params and params[0] == 0:
        return ["'repeat 0' divides by zero in the firmware; the rate must be 1 or more"]
    if len(params) == 2 and params[0] == 0:
        return [f"'{name} 0 {params[1]}': the firmware reads a packed 0 as no parameters, so the second one is lost"]
    return []
