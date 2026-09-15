# QuadStick profile file formats (verified against real files)

Everything below was checked byte-for-byte against `fixtures/ddfortnite.csv` and
`fixtures/cod.csv` (copied off a QuadStick flash drive) and their Google Sheet
sources `ddfortnite.xlsx` / `Call_of_Duty.xlsx`. `tests/test_roundtrip.py` proves
the parser and writer reproduce them exactly. Do not change `write_csv` without
keeping those tests green.

## The model behind both formats

```
File (one .csv on the QuadStick flash drive; the QuadStick calls it a "configuration"
│    or "profile"; selected by long hard sip on the side tube + joystick + lip press)
└── Mode 1..16   (one Google-Sheet tab each; tab order = mode number;
    │             switched instantly by whatever inputs are bound to
    │             increment_mode / decrement_mode; typically side-tube sip/puff)
    └── Row      Output  |  Output function [params]  |  Input(s)
                 what the console sees   how it behaves          what you do with your mouth/joystick
```

An input can appear on many rows (one sip → several outputs). An output can
appear on many rows (several inputs → one output). A row with a blank input is
unused and harmless.

## Google Sheet layout (.xlsx export of the template)

Mode sheet (A1 `Profile Name`; the firmware only checks that the line **starts
with** `Profile`, case-sensitive — same for `Preferences` and `Infrared` — so the
parser accepts any such A1 with an info, and export writes the canonical text):

| cell | content |
|---|---|
| A1 | `Profile Name` |
| C1 | mode label shown to the user, e.g. `Left joy`, `D-Pad` |
| A2 | CSV filename, **first mode sheet only**, e.g. `ddfortnite.csv` |
| C2 | `Normal` |
| A3 | `Output or Function` (PlayStation names) **or** `XBox Outputs` (Xbox names) |
| B3 | `Function` |
| C3 | `usb` or `bluetooth` |
| A4.. | output name |
| B4.. | output function, optionally with numeric params: `repeat 5 2000` |
| C4..J | input(s). C is the input; D–J hold extra inputs for sequences |
| K.. | free-text comments (never exported to the device) |

The first blank A cell ends the sheet: rows after it are ignored by the device.

Sheet (tab) names are Excel's business, not the device's: `write_xlsx` replaces
`[ ] : * ? / \` with `-`, cuts at 31 characters and appends ` 2`, ` 3`, … to a
duplicate (case-insensitive, and `Preferences` is reserved), so a mode called
`A/B?` still exports. The C1 label, which is what the device shows, is untouched.
Older Xbox templates carry an "Alternate" block in K–R (K1 label, K2 `Alternate`,
K3 `usb`); the device treats it as comments. The parser ignores it and says so.

Other sheets: `Preferences` (A1 `Preferences`, header row 3 `Preference | Value |
Units | Description`, values from row 4; value is in **column B**), and an
optional `Reference Card` sheet (human-only, hand-maintained, never exported —
and in `ddfortnite.xlsx` it is stale, still describing Destiny). The official
template also carries `Inputs`, `Outputs` and `Voice` tabs (the dropdown lists);
the add-on skips them and so does the parser (name match, case-insensitive). Any
other sheet whose A1 is not a known header is an error.

### Per-mode preference override rows

Inside a mode block, a row whose **A** cell is a preference key (one of the 61 in
`core/qsprofile/preferences.py`) is not a mapping. The device reads it as "set this
preference while this mode is active", taking the value from **column C**:

```
sip_puff_threshold,,55,       <- in a mode block: threshold 55 for this mode only
mouse_speed,,120,
```

How the firmware decides what a row is (and the order the parser follows):

1. Column A is matched against the **output keywords** first. A name that is both an
   output and a preference is an output row, never an override; on the device that is
   `digital_out_1..4`. The app's catalog lists them as outputs (`catalog.DIGITAL_OUT`,
   the same name on both consoles), so the parser reads `digital_out_1,,1,` in a mode
   as a mapping whose input `1` is unknown, exactly what the device does with it.
2. Otherwise, if column A is a **preference name**, the row is an override. **Column B
   is ignored** by the firmware on such a row; the value is always column C, read with
   `atoi`, so a word there becomes 0. `mouse_speed,normal,120,` is therefore a valid
   override of 120 on the device. The parser keeps whatever B held (in
   `Mapping.function`) so the file round-trips byte for byte, and the validator warns
   that it does nothing.
3. Anything else is a mapping row (an unknown name is an error).

Precedence is `prefs.csv` (global) < the profile's `Preferences` sheet < a per-mode
override row. The form comes from QCM's `docs/FORMAT.md` and the firmware source; it is
**not yet verified on one of the owner's devices**, so the parser keeps such a row
(`Mapping.kind == "preference"`, value in `Mapping.value`), `write_csv` / `write_xlsx`
emit it back unchanged, the validator warns on every one, and the editor shows them
read-only. `fixtures/synthetic_pref_override.csv` is the hand-built example.

## Device CSV (what the add-on's "Save as CSV" / QMP writes)

ASCII, **CRLF** line endings, every data line ends with a **trailing comma**.

```
QuadStick Configuration,Version 1.4,<google sheet url or blank>,<sheet title>
Profile Name,,Left joy,
ddfortnite.csv,,Normal,            <- filename only in the first block; later blocks: ,,Normal,
Output or Function,Function,usb,
increment_mode,normal,right_sip,
dpad_N,normal,                     <- unused row: output,function, and nothing else
...
                                   <- one empty line between blocks
Profile Name,,Left joy,
,,Normal,
...
Preferences,
,,,,
Preference,Value,Units,Description,
digital_out_1,1,on/off,Initial output state for relay 1,
digital_out_2,1,on/off,Initial output state for relay 2,
                                   <- file ends with an empty line
```

Not exported: comments (K+), the Reference Card sheet, blank padding rows.

### What ends a block (firmware rule, differs from the sheet)

The firmware ends a mode only at an **empty line** (first byte CR or LF). A
comma-only line (`,,,,`) or a data line with an empty first field is **skipped**,
not a terminator, and any line between the empty line and the next `Profile` /
`Preferences` / `Infrared` header is never read. `parse_csv` follows that: a
skipped row is dropped with an info (a warning if its other cells were filled,
since they are lost), and a line after the empty line is an **error** ("Line N
comes after the empty line that ended mode M; the QuadStick ignores it"). The
`.xlsx` path keeps the add-on's rule — the first blank A cell ends the sheet —
because that is what the add-on and QMP do when they build the CSV.
Reserved filenames: `default.csv` (always file #1; a broken one can hide the
flash drive until a hardware reset) and `prefs.csv` (global preferences).

## `prefs.csv` (global preferences, what QMP writes)

The firmware's `Load_Preferences_File` reads the file only when **line 1 starts with
`QuadStick`**; it then skips the next three lines and reads `name,value` rows until
the end. A file that starts with a bare `Preferences,` block (the form a profile
carries, and what `write_prefs_csv` used to write) is ignored and the device boots
its built-in defaults. `write_prefs_csv` writes exactly the QMP layout:

```
QuadStick Configuration,Version 1.1     <- no trailing comma on this line
Preferences,,,,
prefs.csv,,,,
Preference,Value,Units,Description,
volume,40,,,
sip_puff_threshold,55,,,
                                        <- file ends with an empty line
```

`read_prefs_csv` accepts both layouts (it is `parse_csv` plus a check that no mode
blocks are present). **Not yet verified against a `prefs.csv` copied off a real
device.**

## Naming sets

PlayStation and Xbox names are two labels for the same 13 gamepad functions; the
device just reads a different header. `catalog.XBOX_TO_PS` is the complete table.
Internally everything is stored under the PlayStation name (canonical). The PS
`touch` (touchpad) output has no Xbox equivalent. A "PC" profile is just a
gamepad-named profile run in emulation mode 0/2/3; true keyboard/mouse profiles
use `kb_*` / `mouse_*` outputs and cannot be auto-converted from buttons without
a per-game keybinding table (a later feature).
