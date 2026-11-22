"""The `qstest` profile and the spec the tester page reads, from one table.

The tester page (web `/tester`) reads the QuadStick's raw USB reports and shows,
live, which tube registered a sip or a puff, how hard, and where the joystick is.
A report says neither which mode the device is in nor which tube pressed a
button, so the tester needs a purpose-built profile:

- every mode HOLDS one d-pad direction (input `constant`), so the page reads the
  mode off the hat nibble. The d-pad holds one direction at a time (measured on
  the device), so each marker is a single direction;
- in every mode each tested input drives its own gamepad button, so the page can
  turn "bit 0x01 of byte 6" back into "hard sip, left tube";
- in every mode the joystick drives the left stick (its values always show) and
  the side tube changes mode (sip = next, puff = previous), as in most profiles.

    mode 1  Joystick        N    stick + lip
    mode 2  Hard            E    hard sip / puff on each mouthpiece tube + lip
    mode 3  Gentle          S    gentle sip / puff on each tube + lip
    mode 4  Combinations    W    two tubes at once (left+centre, right+centre),
                                 hard and gentle; gentle side-tube sip / puff
    mode 5  Everything      NE   all twelve single-tube inputs + lip at once:
                                 shows whether a hard sip ALSO fires the gentle one

`config()` builds the device profile and `spec()` the page's map. Both read the
tables below, so the button-bit -> tube mapping on the page cannot drift from the
file on the device. Ported from the dronecontrol tester
(`tools/make_qstest_profile.py`); the profile it produced is
`fixtures/qstest.csv`, and `tests/test_tester.py` holds this module to it.
"""
from .model import Config, Mapping, Mode

NAME = "qstest"
FILENAME = "qstest.csv"

# Gamepad output -> (report byte, bit) in the 64-byte PS4-layout input report the
# QuadStick sends (byte 0 is the report id 0x01). Confirmed on the unit for
# square / x / circle / triangle / left_1.
BITS = {
    "square": (5, 0x10), "x": (5, 0x20), "circle": (5, 0x40), "triangle": (5, 0x80),
    "left_1": (6, 0x01), "right_1": (6, 0x02), "left_2": (6, 0x04), "right_2": (6, 0x08),
    "select": (6, 0x10), "start": (6, 0x20), "left_3": (6, 0x40), "right_3": (6, 0x80),
    "ps3": (7, 0x01), "touch": (7, 0x02),
}

# The hat value (low nibble of byte 5) each d-pad output holds. Released reads 15.
HAT = {"dpad_N": 0, "dpad_NE": 1, "dpad_E": 2, "dpad_SE": 3, "dpad_S": 4,
       "dpad_SW": 5, "dpad_W": 6, "dpad_NW": 7}


def _inputs():
    """Every input the profile tests -> what the page shows for it."""
    out = {}
    for tube in ("left", "center", "right"):
        for action in ("sip", "puff"):
            for soft in (False, True):
                out[f"mp_{tube}_{action}" + ("_soft" if soft else "")] = {
                    "tubes": [tube], "action": action, "level": "gentle" if soft else "hard"}
    for pair in ("left_center", "right_center"):
        for action in ("sip", "puff"):
            for soft in (False, True):
                out[f"mp_{pair}_{action}" + ("_soft" if soft else "")] = {
                    "tubes": pair.split("_"), "action": action, "level": "gentle" if soft else "hard"}
    for action in ("sip", "puff"):
        out[f"right_{action}_soft"] = {"tubes": ["side"], "action": action, "level": "gentle"}
    out["lip"] = {"tubes": ["lip"], "action": "press", "level": ""}
    return out


INPUTS = _inputs()

_SINGLE_HARD = [("left_1", "mp_left_sip"), ("square", "mp_left_puff"),
                ("triangle", "mp_center_sip"), ("x", "mp_center_puff"),
                ("right_1", "mp_right_sip"), ("circle", "mp_right_puff")]
_SINGLE_SOFT = [(o, i + "_soft") for o, i in _SINGLE_HARD]

# Rows every mode starts with, in this order: mode change on the side tube, and the
# joystick on the left stick.
COMMON = [("increment_mode", "right_sip"), ("decrement_mode", "right_puff"),
          ("left_joy_left", "left"), ("left_joy_right", "right"),
          ("left_joy_up", "up"), ("left_joy_down", "down")]

MODES = [
    {"n": 1, "name": "Joystick", "marker": "dpad_N",
     "help": "Move the joystick up, down, left and right. The values show live. "
             "The lip button works too.",
     "map": [("touch", "lip")]},
    {"n": 2, "name": "Hard sips & puffs", "marker": "dpad_E",
     "help": "A firm sip or puff on any of the three mouthpiece tubes.",
     "map": _SINGLE_HARD + [("touch", "lip")]},
    {"n": 3, "name": "Gentle sips & puffs", "marker": "dpad_S",
     "help": "A light sip or puff on any of the three mouthpiece tubes.",
     "map": _SINGLE_SOFT + [("touch", "lip")]},
    {"n": 4, "name": "Combinations", "marker": "dpad_W",
     "help": "Two tubes at once: left + centre, or right + centre, hard or gentle. "
             "A gentle sip or puff on the side tube shows here too (a hard one changes mode).",
     "map": [("square", "mp_left_center_puff"), ("x", "mp_left_center_sip"),
             ("circle", "mp_right_center_puff"), ("triangle", "mp_right_center_sip"),
             ("left_1", "mp_left_center_puff_soft"), ("right_1", "mp_left_center_sip_soft"),
             ("left_2", "mp_right_center_puff_soft"), ("right_2", "mp_right_center_sip_soft"),
             ("select", "right_sip_soft"), ("start", "right_puff_soft")]},
    {"n": 5, "name": "Everything", "marker": "dpad_NE",
     "help": "Every single-tube input, hard and gentle, at once. Practise freely. "
             "Shows whether a hard sip also registers as a gentle one on the way.",
     "map": [("left_1", "mp_left_sip"), ("square", "mp_left_puff"),
             ("triangle", "mp_center_sip"), ("x", "mp_center_puff"),
             ("right_1", "mp_right_sip"), ("circle", "mp_right_puff"),
             ("select", "mp_left_sip_soft"), ("left_2", "mp_left_puff_soft"),
             ("right_3", "mp_center_sip_soft"), ("left_3", "mp_center_puff_soft"),
             ("start", "mp_right_sip_soft"), ("right_2", "mp_right_puff_soft"),
             ("touch", "lip")]},
]


def check():
    """The table's own invariants. Raises AssertionError naming the first break."""
    hats = [m["marker"] for m in MODES]
    assert len(hats) == len(set(hats)), "two modes share a d-pad marker"
    for m in MODES:
        outs = [o for o, _ in m["map"]]
        assert len(outs) == len(set(outs)), f"mode {m['n']}: an output is used twice"
        assert m["marker"] in HAT, (m["n"], m["marker"])
        for o, inp in m["map"]:
            assert o in BITS, (m["n"], o)
            assert inp in INPUTS, (m["n"], inp)


def config():
    """The `qstest` device profile, ready for `write_csv`."""
    check()
    modes = []
    for m in MODES:
        rows = COMMON + list(m["map"]) + [(m["marker"], "constant")]
        mappings = [Mapping(row=4 + i, output=o, function="normal", params=[], inputs=[inp])
                    for i, (o, inp) in enumerate(rows)]
        modes.append(Mode(number=m["n"], name=m["name"], label=m["name"], channel="usb",
                          mappings=mappings))
    return Config(name=NAME, filename=FILENAME, modes=modes, console="playstation")


def spec():
    """What the tester page reads: each input's tube and strength, and per mode its
    d-pad marker and which report bit means which input."""
    check()
    return {
        "profile": NAME,
        "filename": FILENAME,
        "inputs": INPUTS,
        "modes": [{"n": m["n"], "name": m["name"], "hat": HAT[m["marker"]], "help": m["help"],
                   "map": [{"out": o, "byte": BITS[o][0], "mask": BITS[o][1], "input": inp}
                           for o, inp in m["map"]]}
                  for m in MODES],
    }
