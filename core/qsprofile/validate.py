"""Validation rules derived from the manual's format constraints, from real
mistakes found in ddfortnite.xlsx, and from the firmware limits observed in
QuadStick Config Manager and the code review. Each finding is
(severity, mode_number|None, row|None, message). Errors block export."""
import re
from collections import defaultdict
from .catalog import (classify_input, output_label, MODE_CHANGE_OUTPUTS,
                     FUNCTIONS, all_mouthpiece_inputs, LEGACY_INPUTS, PREFERENCES,
                     MAX_MODES, MAX_ROWS_PER_MODE, MAX_KEYWORD_CHARS, MAX_LINE_BYTES,
                     DEFAULT_FIRMWARE, EMULATION_MODES, hidden_drive_modes, firmware_phrase,
                     function_errors, check_csv_filename, unsafe_text, MODE_OVERRIDABLE)
from .preferences import THRESHOLD_ORDER

RESERVED = {"default.csv", "prefs.csv"}
CHANNELS = ("usb", "bluetooth", "both", "none")   # what C3 may say (firmware 2373)
CABLE_ONLY = ("kb_", "mouse_")                    # outputs that only exist on the USB cable
COLS = "CDEFGHIJ"
PREF_SCOPES = ("global", "profile", "mode")


def validate(cfg, problems=None, firmware=None):
    """All findings for a Config. `firmware` picks the drive-hiding emulation set
    (catalog.hidden_drive_modes); None means DEFAULT_FIRMWARE."""
    out = list(problems or [])
    err = lambda mode, row, msg: out.append(("error", mode, row, msg))
    warn = lambda mode, row, msg: out.append(("warning", mode, row, msg))
    info = lambda mode, row, msg: out.append(("info", mode, row, msg))
    fw = firmware or DEFAULT_FIRMWARE

    # ---- file level
    bad_name = check_csv_filename(cfg.filename)
    if bad_name:
        err(None, 2, f"A2 on the first sheet must be a filename ending in .csv: {bad_name}")
    else:
        if cfg.filename != cfg.filename.lower():
            info(None, 2, f"The QuadStick lowercases filenames, so the device will call this {cfg.filename.lower()}")
        if cfg.filename.lower() in RESERVED:
            warn(None, 2, f"'{cfg.filename}' is reserved by the QuadStick; a broken default.csv can hide the flash drive")
    if not cfg.modes:
        err(None, None, "No mode sheets found (sheets whose A1 is 'Profile Name')")
    if len(cfg.modes) > MAX_MODES:
        err(None, None, f"{len(cfg.modes)} modes; the QuadStick allows at most {MAX_MODES}")
    # nothing that reaches write_csv may carry a comma, a line break or non-ASCII (D4).
    # Line 1 is special: the firmware only reads its first word, so a comma in the
    # name or URL cannot shift a block, it only truncates the name on re-import.
    for what, value in (("The profile name", cfg.name), ("The sheet URL", cfg.source_url)):
        text = "" if value is None else str(value)
        problem = unsafe_text(text.replace(",", ""))
        if problem:
            err(None, 1, f"{what} '{text[:30]}' {problem}")
        if "," in text:
            warn(None, 1, f"{what} '{text[:30]}' contains a comma; the QuadStick ignores line 1 "
                          "after its first word, but this app will read the name back cut short")

    # ---- the profile's own preference rows (the device applies these, not any app column)
    for f in validate_preferences(cfg.preferences, fw, "profile"):
        out.append(f)

    # ---- emulation mode: the file's own value (Preferences block and per-mode
    # override rows) is what the device applies; there is no other source of truth.
    reserved = (cfg.filename or "").lower() in RESERVED
    hidden = hidden_drive_modes(fw)

    def check_emulation(value, mode, row, where):
        try:
            n = int(str(value).strip())
        except ValueError:
            return                   # validate_preferences reports the bad value
        if n in hidden:
            label = EMULATION_MODES.get(n, "")
            msg = (f"enable_DS3_emulation = {n} ({label}){where} hides the flash drive"
                   f"{firmware_phrase(fw)}; a mistake in this profile needs the side-tube recovery procedure")
            if reserved:
                err(mode, row, msg + f". In {cfg.filename} that applies at every boot, so it must be changed before export")
            else:
                warn(mode, row, msg)

    if "enable_DS3_emulation" in cfg.preferences:
        check_emulation(cfg.preferences["enable_DS3_emulation"], None, None, "")
    for mode in cfg.modes:
        for m in mode.mappings:
            if m.kind == "preference" and m.output == "enable_DS3_emulation":
                check_emulation(m.value, mode.number, m.row, f" (row {m.row}, this mode only)")

    for mode in cfg.modes:
        n = mode.number
        # C3 is exported verbatim, so it gets the D4 text check like every other cell;
        # a word the firmware does not know is an error, an empty cell exports as usb.
        channel = mode.channel or ""
        problem = unsafe_text(channel)
        if problem:
            err(n, 3, f"C3 '{channel[:30]}' {problem}")
        elif not channel:
            warn(n, 3, f"C3 is empty; expected one of {', '.join(CHANNELS)}. Export writes usb")
        elif channel not in CHANNELS:
            err(n, 3, f"C3 is '{channel}'; the QuadStick expects one of {', '.join(CHANNELS)}")
        elif channel in ("bluetooth", "none"):
            cabled = [m for m in mode.mappings if m.kind == "mapping" and m.output.startswith(CABLE_ONLY)]
            if cabled:
                warn(n, cabled[0].row, f"Not connected by USB (C3 is {mode.channel}), so kb_/mouse_ "
                                       f"outputs will not reach the cable: rows {', '.join(str(m.row) for m in cabled)}")
        problem = unsafe_text(mode.label)
        if problem:
            err(n, 1, f"The mode label (C1) '{mode.label[:30]}' {problem}")
        if len(mode.mappings) > MAX_ROWS_PER_MODE:
            err(n, None, f"This mode ({mode.name}) has {len(mode.mappings)} rows; the firmware reads at most "
                         f"{MAX_ROWS_PER_MODE} per mode")
        by_input = defaultdict(list)       # input -> [(output, row)]
        seen_pairs = defaultdict(list)     # (input, output) -> rows
        overrides = {}                     # per-mode preference rows: key -> (value, row)
        exits = False
        for m in mode.mappings:
            # firmware limits apply to every keyword and to the exported line
            for kw in [m.output, m.function, *m.inputs]:
                if len(kw) > MAX_KEYWORD_CHARS:
                    err(n, m.row, f"'{kw[:20]}…' is {len(kw)} characters; the firmware reads at most {MAX_KEYWORD_CHARS}")
            cells = [m.output, m.function, *map(str, m.params), *m.inputs, m.value]
            for cell in cells:
                problem = unsafe_text(cell)
                if problem:
                    err(n, m.row, f"Row {m.row}: '{cell[:30]}' {problem}")
            line = ",".join([m.output, m.function + " " + " ".join(map(str, m.params)), *m.inputs, m.value]) + ","
            if len(line.encode("ascii", "replace")) > MAX_LINE_BYTES:
                err(n, m.row, f"Row {m.row} exports as {len(line)} bytes; the firmware reads at most {MAX_LINE_BYTES} per line")
            if m.kind == "preference":
                pref = PREFERENCES.get(m.output)
                what = f" ({pref['description']})" if pref else ""
                # Information, not a warning: a per-mode preference row is a
                # documented, deliberate feature, and profiles in the wild use it.
                # The "not verified" note is about this app's knowledge, not about
                # the file — flagging it as a problem blamed the owner for ours.
                info(n, m.row, f"Row {m.row} sets {m.output} = {m.value} for this mode only{what}. "
                               "Per-mode preference overrides are documented but not yet verified on a device")
                if m.function:
                    warn(n, m.row, f"Row {m.row}: column B '{m.function}' does nothing on a preference row; "
                                   f"the QuadStick ignores it and reads the value from column C ('{m.value}')")
                for sev, _, _, msg in validate_preferences({m.output: m.value}, fw, "mode"):
                    out.append((sev, n, m.row, f"Row {m.row}: {msg}"))
                overrides[m.output] = (m.value, m.row)
                continue
            if output_label(m.output) is None:
                err(n, m.row, f"Unknown output '{m.output}'")
            if not m.function:
                info(n, m.row, f"Row {m.row} has no function; the QuadStick treats it as normal")
            else:
                for e in function_errors(m.function, m.params):
                    err(n, m.row, f"Row {m.row}: {e}")
            for ix, inp in enumerate(m.inputs):
                c = classify_input(inp)
                if c is None:
                    col = COLS[ix]
                    if " " in inp or len(inp) > 24:
                        err(n, m.row, f"Column {col} looks like a comment ('{inp[:30]}…') but is read as an input; move comments to column K or later")
                    else:
                        err(n, m.row, f"Unknown input '{inp}' in column {col}")
                elif c["kind"] == "legacy":
                    warn(n, m.row, f"'{inp}' is an older input name ({LEGACY_INPUTS[inp]}); firmware 2373 still accepts it")
            if m.is_sequence():
                info(n, m.row, f"Row {m.row} is a sequence: {' then '.join(m.inputs)} (performed in that order) → {m.output}")
            if m.inputs:
                by_input[m.inputs[0]].append((m.output, m.row))
                seen_pairs[(m.inputs[0], m.output)].append(m.row)
                if m.output in MODE_CHANGE_OUTPUTS:
                    exits = True
        # override rows that only make sense together (threshold ordering)
        for key, msg in threshold_findings({k: v for k, (v, _) in overrides.items()}):
            err(n, overrides[key][1], f"Row {overrides[key][1]}: {msg}")
        # firmware behaviours worth a word (QCM warns on the same three)
        def effective(key, default):
            v = overrides[key][0] if key in overrides else cfg.preferences.get(key, default)
            v = _as_int(v)
            return default if v is None else v
        emulation = effective("enable_DS3_emulation", 0)
        dead_zone_shape = effective("joystick_dead_zone_shape", 1)
        for m in mode.active():
            if m.output == "reset_quadstick" and "push" in m.inputs:
                warn(n, m.row, f"Row {m.row} binds reset_quadstick to push: the firmware waits 300 ms and, if the "
                               "push switch is still held, drops into the serial bootloader until power-cycled")
            if "any_direction" in m.inputs and dead_zone_shape == 0:
                warn(n, m.row, f"Row {m.row} uses any_direction while joystick_dead_zone_shape is 0 (square); "
                               "the firmware then reports the stick as always moved, so this row is stuck on")
            if m.output in ("left_2", "right_2") and emulation in (2, 3):
                warn(n, m.row, f"Row {m.row} presses {m.output} in emulation mode {emulation} "
                               f"({EMULATION_MODES.get(emulation, '')}): Xbox triggers are an axis there and "
                               "arrive as 1 of 255, which most games ignore")
        # duplicates and conflicts
        for (inp, o), rows in seen_pairs.items():
            if len(rows) > 1:
                warn(n, rows[1], f"'{inp}' → {o} is mapped twice (rows {', '.join(map(str, rows))})")
        for inp, lst in by_input.items():
            outs = [o for o, _ in lst]
            mode_changes = [o for o in outs if o in MODE_CHANGE_OUTPUTS]
            actions = [o for o in outs if o not in MODE_CHANGE_OUTPUTS]
            if mode_changes and actions:
                r = [row for o, row in lst if o in MODE_CHANGE_OUTPUTS][0]
                # Information, not a warning. One input that does something *and*
                # changes mode is a normal, deliberate design — the owner's own
                # profile uses a chin press to fire an action and hop to the mode
                # that presses it again to come back. The file is worth describing
                # so nobody is surprised by it, but there is nothing here to fix.
                info(n, r, f"'{inp}' triggers {', '.join(actions)} AND {', '.join(mode_changes)}: "
                           "the game action fires at the same moment the mode switches")
        if not exits:
            warn(n, None, f"This mode ({mode.name}) has no increment_mode / decrement_mode / load_file — you can't leave it")
        # toggles that never get released elsewhere
        toggled = {m.output for m in mode.active() if m.function == "toggle"}
        forced = {m.output for m in mode.active() if m.function == "force_off"}
        for o in toggled - forced:
            info(n, None, f"{o} is a toggle with no force_off; it only releases when you toggle again or change mode")
        # movement coverage
        sticks = [m for m in mode.active() if m.output.startswith(("left_joy", "right_joy", "dpad"))]
        if not sticks:
            info(n, None, f"This mode ({mode.name}) drives no stick or D-pad; the joystick does nothing here")
        # empty duplicate rows
        blank_dupes = defaultdict(int)
        for m in mode.mappings:
            if not m.inputs and m.kind == "mapping":
                blank_dupes[m.output] += 1
        for o, c in blank_dupes.items():
            if c > 1:
                info(n, None, f"{o} appears {c} times with no input (harmless, but clutter)")

    # reference card staleness
    if cfg.reference_card:
        text = " ".join(" ".join(r) for r in cfg.reference_card)
        m = re.search(r"\(([\w\-]+\.csv)\)", text)
        if m and m.group(1).lower() != (cfg.filename or "").lower():
            warn(None, None, f"The 'Reference Card' sheet describes {m.group(1)}, not {cfg.filename}; it is hand-maintained and out of date")
        listed = [c for c in cfg.reference_card[-1] if c and c != "Mode:"] if cfg.reference_card else []
        missing = [md.name for md in cfg.modes if md.name not in listed]
        if listed and missing:
            warn(None, None, f"Reference Card lists modes {listed} but the file also has {missing}")

    # collapse repeats of the same informational note across modes
    seen, deduped = set(), []
    for p in out:
        key = (p[0], re_key(p[3]))
        if p[0] == "info" and key in seen:
            continue
        seen.add(key); deduped.append(p)
    out = deduped
    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda p: (order[p[0]], p[1] or 0, p[2] or 0))
    return out


def re_key(msg):
    return re.sub(r"^(Mode|Row) \d+[^:]*: ?", "", msg)


# ---------------------------------------------------------------- preferences
def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def threshold_findings(prefs):
    """[(key_to_blame, message)] for pairs in THRESHOLD_ORDER that are out of order.
    Only pairs present in the same dict are compared; the blamed key is the higher one."""
    out = []
    for lo_key, gap, hi_key, zero_unset in THRESHOLD_ORDER:
        if lo_key not in prefs or hi_key not in prefs:
            continue
        lo, hi = _as_int(prefs[lo_key]), _as_int(prefs[hi_key])
        if lo is None or hi is None:
            continue                      # the type rule reports those
        if zero_unset and (lo == 0 or hi == 0):
            continue
        if lo + gap > hi:
            lo_label, hi_label = PREFERENCES[lo_key]["label"], PREFERENCES[hi_key]["label"]
            out.append((hi_key, f"{hi_label} ({hi_key}) is {hi} but must be at least {gap} above "
                                f"{lo_label} ({lo_key}), which is {lo}; the QuadStick needs that gap to tell them apart"))
    return out


def validate_preferences(prefs, firmware=None, scope="profile"):
    """Findings for a {key: value} preference set, stated in device terms.

    scope: "global" (prefs.csv, applies at every boot), "profile" (the Preferences
    block) or "mode" (a per-mode override row, which the firmware reads with atoi).
    Findings carry mode=None, row=None; the caller re-tags them for override rows."""
    if scope not in PREF_SCOPES:
        raise ValueError(f"scope must be one of {PREF_SCOPES}")
    fw = firmware or DEFAULT_FIRMWARE
    out = []
    err = lambda msg: out.append(("error", None, None, msg))
    warn = lambda msg: out.append(("warning", None, None, msg))
    info = lambda msg: out.append(("info", None, None, msg))
    for key, value in prefs.items():
        value = "" if value is None else str(value)
        problem = unsafe_text(key)
        if problem:
            err(f"The setting name '{key[:30]}' {problem}")
            continue
        meta = PREFERENCES.get(key)
        if meta is None:
            info(f"'{key}' is not a setting this app knows; it is stored and exported as it is")
            problem = unsafe_text(value)
            if problem:
                err(f"{key} = '{value[:30]}' {problem}")
            continue
        label, editor = meta["label"], meta.get("editor")
        problem = unsafe_text(value)
        if problem:
            err(f"{label} ({key}) = '{value[:30]}' {problem}")
            continue
        if scope == "mode":
            if key not in MODE_OVERRIDABLE:
                warn(f"{label} ({key}) cannot be set per mode; the device ignores this here")
            if _as_int(value) is None:
                err(f"{label} ({key}) must be a whole number in a per-mode row; the device reads it "
                    f"with atoi, so '{value}' would become 0")
                continue
        if editor in ("integer", "toggle"):
            n = _as_int(value)
            if n is None:
                err(f"{label} ({key}) must be a whole number, got '{value}'")
                continue
            lo, hi = meta.get("minimum"), meta.get("maximum")
            if editor == "toggle":
                lo, hi = 0, 1
            if lo is not None and n < lo:
                err(f"{label} ({key}) is {n}; the lowest the QuadStick accepts is {lo}")
            if hi is not None and n > hi:
                err(f"{label} ({key}) is {n}; the highest the QuadStick accepts is {hi}")
        elif editor == "choice":
            options = meta.get("options") or []
            numeric = all(o.lstrip("-").isdigit() for o in options)
            if options and value not in options and (scope != "mode" or numeric):
                err(f"{label} ({key}) is '{value}'; it must be one of {', '.join(options)}")
    for _, msg in threshold_findings(prefs):
        err(msg)
    if scope == "global":
        n = _as_int(prefs.get("enable_DS3_emulation"))
        if n is not None and n in hidden_drive_modes(fw):
            err(f"enable_DS3_emulation = {n} ({EMULATION_MODES.get(n, '')}) hides the flash drive"
                f"{firmware_phrase(fw)}. Set device-wide in prefs.csv, that applies to every profile at every "
                "boot, so a mistake needs the side-tube recovery; change it before export")
    return out


def unused_inputs(mode):
    used = {i for m in mode.active() for i in m.inputs}
    pool = list(all_mouthpiece_inputs()) + ["right_sip", "right_puff", "right_sip_soft",
                                            "right_puff_soft", "lip", "lip_soft", "digital_in_1", "digital_in_2"]
    return [i for i in pool if i not in used]


def budget(cfg, firmware=None):
    """Firmware capacity used by this profile, for the editor's budget counters."""
    from .catalog import MAX_PREFERENCE_ROWS, DEFAULT_FIRMWARE
    fw = firmware or DEFAULT_FIRMWARE
    return {
        "modes_used": len(cfg.modes), "modes_max": MAX_MODES,
        "rows_max": MAX_ROWS_PER_MODE,
        "modes": [{"number": m.number, "name": m.name, "rows_used": len(m.mappings),
                   "rows_free": max(0, MAX_ROWS_PER_MODE - len(m.mappings)),
                   "rows_active": len(m.active()), "unused_inputs": unused_inputs(m)} for m in cfg.modes],
        "preference_rows": len(cfg.preferences),
        "preference_rows_max": MAX_PREFERENCE_ROWS.get(fw, MAX_PREFERENCE_ROWS[DEFAULT_FIRMWARE]),
    }
