"""Convert a profile between console naming sets, and write it back out as a
workbook in the Google Sheet template layout.

Because the QuadStick's PlayStation and Xbox names are two labels for one set
of underlying gamepad functions, conversion is a rename plus a check for
outputs the target has no name for (e.g. the PS touchpad)."""
import copy
import re
from openpyxl import Workbook
from .catalog import display_output, NO_XBOX_EQUIVALENT, PREFERENCES, PS_BUTTONS

HEADER_A3 = {"playstation": "Output or Function", "xbox": "XBox Outputs"}
_BAD_TITLE = re.compile(r"[\[\]:*?/\\]")      # what Excel (and openpyxl) refuse in a sheet name
MAX_SHEET_TITLE = 31


def sheet_title(name, used, fallback):
    """A sheet name Excel accepts: no []:*?/\\, at most 31 characters, unique among
    `used` (Excel compares case-insensitively). A clash gets ' 2', ' 3', ... appended
    inside the limit. Adds the chosen title to `used` and returns it."""
    base = _BAD_TITLE.sub("-", name).strip()[:MAX_SHEET_TITLE].rstrip() or fallback
    title, n = base, 1
    while title.lower() in used:
        n += 1
        suffix = f" {n}"
        title = base[:MAX_SHEET_TITLE - len(suffix)].rstrip() + suffix
    used.add(title.lower())
    return title


def convert(cfg, target):
    """Returns (new_cfg, notes). Outputs are canonical internally, so this only
    changes cfg.console and reports anything that won't carry across."""
    new = copy.deepcopy(cfg)
    new.console = target
    notes = []
    if target == "xbox":
        for mode in new.modes:
            for m in mode.active():
                if m.output in NO_XBOX_EQUIVALENT:
                    notes.append(("warning", mode.number, m.row,
                                  f"'{m.output}' has no Xbox equivalent; row kept but the input will do nothing on Xbox"))
    return new, notes


def write_xlsx(cfg, path, filename=None):
    """Write the config in the template layout (A1 type, A2 filename, A3 header,
    rows from 4, comments in K)."""
    wb = Workbook()
    wb.remove(wb.active)
    used = {"preferences"}                       # that sheet comes last and keeps its name
    for mode in cfg.modes:
        ws = wb.create_sheet(sheet_title(mode.name or mode.label, used, f"Mode {mode.number}"))
        ws["A1"], ws["C1"] = "Profile Name", mode.label
        if mode.number == 1:
            ws["A2"] = filename or cfg.filename
        ws["C2"] = "Normal"
        ws["A3"], ws["B3"], ws["C3"] = HEADER_A3[cfg.console], "Function", mode.channel or "usb"
        r = 4
        for m in mode.mappings:
            if m.kind == "preference":            # A = key, B as read (ignored by the device), C = value
                ws.cell(r, 1, m.output); ws.cell(r, 3, m.value)
                if m.function:
                    ws.cell(r, 2, m.function)
                if m.comment:
                    ws.cell(r, 11, m.comment)
                r += 1
                continue
            ws.cell(r, 1, display_output(m.output, cfg.console))
            fn = m.function + ("" if not m.params else " " + " ".join(str(p) for p in m.params))
            ws.cell(r, 2, fn)
            for i, inp in enumerate(m.inputs[:8]):
                ws.cell(r, 3 + i, inp)
            if m.comment:
                ws.cell(r, 11, m.comment)
            r += 1
    ws = wb.create_sheet("Preferences")
    ws["A1"] = "Preferences"
    ws["A3"], ws["B3"], ws["C3"], ws["D3"] = "Preference", "Value", "Units", "Description"
    r = 4
    for k, v in cfg.preferences.items():
        ws.cell(r, 1, k); ws.cell(r, 2, v); r += 1
    wb.save(path)


def write_csv(cfg, path, filename=None, source_url=None):
    """Write the device CSV exactly as the QuadStick add-on does (see parser.parse_csv)."""
    fname = filename or cfg.filename
    lines = [f"QuadStick Configuration,{cfg.format_version or 'Version 1.4'},"
             f"{source_url if source_url is not None else cfg.source_url},{cfg.name}"]
    for mode in cfg.modes:
        lines.append(f"Profile Name,,{mode.label},")
        lines.append(f"{fname if mode.number == 1 else ''},,Normal,")
        lines.append(f"{HEADER_A3[cfg.console]},Function,{mode.channel or 'usb'},")
        for m in mode.mappings:
            if m.kind == "preference":            # per-mode override: key,<B as read>,value,
                lines.append(f"{m.output},{m.function},{m.value},")
                continue
            fn = m.function + ("" if not m.params else " " + " ".join(str(p) for p in m.params))
            cells = [display_output(m.output, cfg.console), fn] + list(m.inputs[:8])
            lines.append(",".join(cells) + ",")
        lines.append("")
    lines.append("Preferences,")
    lines.append(",,,,")
    lines.append("Preference,Value,Units,Description,")
    for k, v in cfg.preferences.items():
        units, desc = PREF_META.get(k, ("", ""))
        lines.append(f"{k},{v},{units},{desc},")
    lines.append("")
    _write_device_lines(lines, path)


def _write_device_lines(lines, path):
    """CRLF endings, strict ASCII. Encode before opening the target: the encode is
    what raises on non-ASCII, and opening first left a 0-byte file (or clobbered a
    good one) behind a failed write."""
    data = ("\r\n".join(lines) + "\r\n").encode("ascii", errors="strict")
    with open(path, "wb") as f:
        f.write(data)


PREF_META = {
    "digital_out_1": ("on/off", "Initial output state for relay 1"),
    "digital_out_2": ("on/off", "Initial output state for relay 2"),
}


PREFS_HEADER = ["QuadStick Configuration,Version 1.1", "Preferences,,,,", "prefs.csv,,,,",
                "Preference,Value,Units,Description,"]


def write_prefs_csv(preferences, path):
    """Write the device's global `prefs.csv` in the layout QMP writes.

    The firmware's Load_Preferences_File reads the file only when line 1 starts with
    `QuadStick`; it then skips the next three lines (`Preferences,,,,`, `prefs.csv,,,,`
    and the column header) before reading `name,value` rows. Anything else — including
    the bare Preferences block a profile carries, which this used to write — is ignored
    and the device boots its built-in defaults. Same CRLF endings, trailing commas and
    ASCII as `write_csv`; the Units / Description columns are filled from PREFERENCES so
    the file reads the way QMP's does.
    """
    lines = list(PREFS_HEADER)
    for k, v in preferences.items():
        units, desc = PREF_META.get(k, ("", ""))
        if not units and k in PREFERENCES:
            units = PREFERENCES[k].get("unit", "") or ""
        lines.append(f"{k},{v},{units},{desc},")
    lines.append("")
    _write_device_lines(lines, path)


def read_prefs_csv(path):
    """Read a `prefs.csv` into {key: value}, plus findings for anything unexpected.

    Unknown keys are kept — the device may know settings this catalog does not — but
    reported, because a typo would otherwise be silently carried along.
    """
    from .parser import parse_csv

    cfg, problems = parse_csv(path)
    findings = list(problems)
    if cfg.modes:
        findings.append(("warning", None, None,
                         f"{len(cfg.modes)} profile mode(s) found in a preferences file; "
                         "they are ignored. Is this a profile .csv rather than prefs.csv?"))
    for key in cfg.preferences:
        if key not in PREFERENCES:
            findings.append(("info", None, None,
                             f"'{key}' is not a preference this app knows; it is kept as it is"))
    return cfg.preferences, findings


if __name__ == "__main__":
    import sys
    from .parser import load
    from .validate import validate
    src, target, out = sys.argv[1], sys.argv[2], sys.argv[3]
    newname = sys.argv[4] if len(sys.argv) > 4 else None
    cfg, problems = load(src)
    new, notes = convert(cfg, target)
    if out.lower().endswith(".csv"):
        write_csv(new, out, newname)
    else:
        write_xlsx(new, out, newname)
    print(f"{cfg.console} -> {target}: {len(new.modes)} modes written to {out}")
    for n in notes + [p for p in validate(cfg, problems) if p[0] == "error"]:
        print(" ", n)
