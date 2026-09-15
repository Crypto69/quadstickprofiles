"""Render a Config as a printable HTML reference card.

Design: the per-mode tube grid is the hero — rows are what you do with your
mouth (soft puff / puff / sip / soft sip), columns are which hole(s). Sip and
puff are colour-coded so the card can be read from the sofa. Everything else
is quiet. A4 portrait, one page per mode, first page = orientation.
"""
import html
import json
from .catalog import (classify_input, PS_BUTTONS, XBOX_GLYPH, output_label, output_group,
                     TUBES, TUBE_ORDER, JOY_ZONES, MODE_CHANGE_OUTPUTS)
from .validate import unused_inputs

GLYPH = dict(PS_BUTTONS)
GLYPH.update({"increment_mode": "Mode +", "decrement_mode": "Mode –", "load_file": "File"})
STRENGTH_ROWS = [("puff", "soft", "Soft puff"), ("puff", "hard", "Puff"),
                 ("sip", "hard", "Sip"), ("sip", "soft", "Soft sip")]


def esc(s):
    return html.escape(str(s))


def action_for(actions, mode, output):
    per_mode = actions.get("modes", {}).get(mode.name, {})
    return per_mode.get(output) or actions.get("outputs", {}).get(output, "")


def fn_tag(m):
    if m.function in ("normal", ""):          # an empty cell is normal to the device
        return ""
    # params are free text by design (the parser keeps a bad token so the editor can
    # show the row), and an imported function name need not be a known keyword, so
    # both are escaped here like every other user string on the card.
    p = esc(" ".join(str(x) for x in m.params))
    words = {"toggle": "toggle", "repeat": "auto-fire", "pulse": "tap", "delay_on": "after delay",
             "delay_off": "held after release", "tap": "tap", "delayed_latch": "hold to latch",
             "force_off": "release", "duty": "pressure", "greater_than": "above",
             "less_than": "below", "increment_value": "step up", "decrement_value": "step down"}
    word = esc(words.get(m.function, m.function))
    return f'<span class="fn">{word}{(" " + p) if p else ""}</span>'


def glyphs(console):
    """Button glyph table for a console. Outputs are stored under PlayStation
    names; `console` is the profile attribute applied here, at display time,
    and is threaded through every helper rather than kept in module state so
    two cards rendered in either order come out the same."""
    return {**GLYPH, **XBOX_GLYPH} if console == "xbox" else GLYPH


def seq_tag(m):
    """Rows with 2+ inputs are a sequence performed in column order; the chip sits under
    the LAST input and says what must come before it."""
    if not m.is_sequence():
        return ""
    before = " then ".join(input_label(i) for i in m.inputs[:-1])
    return f'<span class="fn seq">after {esc(before)}</span>'


def input_label(name):
    c = classify_input(name)
    return c["label"] if c else name


def chip(m, actions, mode, console):
    """One button in the tube grid: what it produces, plus what it means.

    Two different things can name a row, and a chip shows both. The *action* comes
    from the actions file and is the same for everyone playing that game ("Lethal
    equipment"); the *note* is the owner's own Note column and says what they use it
    for ("Lethal e.g Grenade"). Plenty of rows have only one of the two — a note with
    no action ("Resupply from teamate") is the only label that row will ever get, so
    dropping it leaves the chip blank.
    """
    label = glyphs(console).get(m.output) or output_label(m.output) or m.output
    act = action_for(actions, mode, m.output)
    cls = "chip " + output_group(m.output)
    # Each line only appears when it has something to say: an empty .act used to
    # leave a blank line, which is visible once a note sits under it. A note that
    # only repeats the action is not worth a second line either.
    lines = ''
    if act:
        lines += f'<span class="act">{esc(act)}</span>'
    if m.comment and m.comment != act:
        lines += f'<span class="act-note">{esc(m.comment)}</span>'
    return (f'<div class="{cls}"><span class="glyph">{esc(label)}</span>'
            f'{fn_tag(m)}{seq_tag(m)}{lines}</div>')


def index_by_input(mode):
    """Bucket active rows by the input they fire on: the only input for plain rows,
    the last input for sequences (the one that completes the pattern)."""
    d = {}
    for m in mode.active():
        d.setdefault(m.inputs[-1], []).append(m)
    return d


def chipped_inputs(mode):
    """The inputs whose rows a mode page draws as chips: the tube grid, the lip
    button and the switch jacks. A row fired by anything else (a stick or D-pad
    direction) is written as prose by joystick_summary instead, so its Note has
    nowhere to ride along and gets listed separately.

    Keyed the way index_by_input buckets rows — by `inputs[-1]`, the input that
    completes a sequence — so a two-input row is judged by the same key that
    decides which cell it is drawn in.
    """
    keys = {"lip", "lip_soft"} | {f"digital_in_{n}" for n in range(1, 9)}
    for c in TUBE_ORDER + ["side"]:
        stem = "right" if c == "side" else f"mp_{c}"
        for act in ("sip", "puff"):
            for strength in ("", "_soft"):
                keys.add(f"{stem}_{act}{strength}")
    return keys


def overrides_summary(mode):
    rows = [m for m in mode.mappings if m.kind == "preference"]
    if not rows:
        return ""
    items = "".join(f"<li><code>{esc(m.output)}</code> = {esc(m.value)}</li>" for m in rows)
    return f'<h2>Settings in this mode</h2><ul class="switch">{items}</ul>'


def tube_grid(mode, actions, console):
    by = index_by_input(mode)
    cols = TUBE_ORDER + ["side"]
    used_cols = [c for c in cols if any(
        by.get(f"{'right' if c == 'side' else 'mp_' + c}_{a}{s}") for a in ("sip", "puff") for s in ("", "_soft"))]
    h = ['<table class="grid"><thead><tr><th class="corner"></th>']
    for c in used_cols:
        h.append(f'<th>{esc("Side tube" if c == "side" else TUBES[c])}</th>')
    h.append("</tr></thead><tbody>")
    for act, strength, title in STRENGTH_ROWS:
        h.append(f'<tr class="{act} {strength}"><th>{title}</th>')
        for c in used_cols:
            key = f"{'right' if c == 'side' else 'mp_' + c}_{act}{'_soft' if strength == 'soft' else ''}"
            ms = by.get(key, [])
            h.append("<td>" + "".join(chip(m, actions, mode, console) for m in ms) + "</td>")
        h.append("</tr>")
    h.append("</tbody></table>")
    return "".join(h)


def joystick_summary(mode, actions, console):
    by = index_by_input(mode)
    lines = []
    dirs = {"up": "forward", "down": "back", "left": "left", "right": "right"}
    stick_of = {}
    for d in dirs:
        for m in by.get(d, []):
            if m.output.startswith(("left_joy", "right_joy")):
                stick_of.setdefault(m.output.split("_joy")[0], []).append(dirs[d])
    for s, ds in stick_of.items():
        which = "Left" if s == "left" else "Right"
        what = action_for(actions, mode, f"{s}_joy_up")
        lines.append(f"<b>{which} stick</b> {esc(what)} ({', '.join(ds)})")
    zones = [z for z in JOY_ZONES if any(m.output.startswith("dpad") for m in by.get(z, []))]
    if zones:
        lines.append("<b>D-pad</b> " + ", ".join(
            f"{z} {esc(action_for(actions, mode, 'dpad_' + z)) or ''}".strip() for z in zones))
    extras = [(d, m) for d in list(dirs) + JOY_ZONES for m in by.get(d, [])
              if not m.output.startswith(("left_joy", "right_joy", "dpad"))]
    for d, m in extras:
        lines.append(f"Pushing <b>{dirs.get(d, d)}</b> also holds {chip(m, actions, mode, console)}")
    if not lines:
        lines.append("Joystick does nothing in this mode")
    return "".join(f"<li>{l}</li>" for l in lines)


def input_name(actions, key, default):
    """Per-profile hardware names, e.g. {"inputs": {"lip": "Chin switch"}}."""
    return actions.get("inputs", {}).get(key, default)


def lip_summary(mode, actions, console):
    by = index_by_input(mode)
    out = []
    lipname = input_name(actions, "lip", "Lip button")
    for key, title in (("lip", "Press"), ("lip_soft", "Soft press")):
        if by.get(key):
            out.append(f'<div class="lip"><span class="lbl">{esc(title)}</span>' +
                       "".join(chip(m, actions, mode, console) for m in by[key]) + "</div>")
    return "".join(out)


def switches_summary(mode, actions, console):
    """External ability switches plugged into the back-panel jacks."""
    by = index_by_input(mode)
    out = []
    for n in range(1, 9):
        key = f"digital_in_{n}"
        if by.get(key):
            c = classify_input(key)
            title = input_name(actions, key, f"Switch {n}")
            out.append(f'<div class="lip"><span class="lbl">{esc(title)}<br><small style="font-weight:400;color:#555">'
                       f'{esc(c["jack"])}</small></span>' +
                       "".join(chip(m, actions, mode, console) for m in by[key]) + "</div>")
    return "".join(out)


def switching(cfg):
    """Derive how modes are switched from mode 1's rows; nothing to say without one."""
    lines = []
    if not cfg.modes:
        return lines
    for m in cfg.modes[0].active():
        if m.output in MODE_CHANGE_OUTPUTS:
            c = classify_input(m.inputs[0])
            lines.append(f"{esc(c['label'] if c else m.inputs[0])} → {esc(GLYPH.get(m.output, m.output))}")
    return lines


LED_COLOURS = ("off", "purple", "blue", "red")
# One letter per lit colour, printed inside the dot so a mono printer (or a
# reader who cannot tell purple from blue) still gets the pattern.
LED_LETTER = {"purple": "P", "blue": "B", "red": "R"}


def leds(n):
    """Status LED colours for mode n, one entry per LED 1..5: 'off'|'purple'|'blue'|'red'.

    Models the firmware's update_active_config_leds. Colour is part of the
    encoding: modes 1–5 light one purple LED; 6–9 light LED 5 purple plus LED
    n−5; 10 is LED 5 blue alone; 11–14 are LED 5 blue plus one purple LED;
    15 is LED 5 red alone; 16 is LED 1 purple plus LED 5 red. The same enum is
    used by the on-screen device view (web/src/device/layout.ts::ledsFor) so
    the card and the screen agree.
    """
    lit = ["off"] * 5
    if 1 <= n <= 5:
        lit[n - 1] = "purple"
    elif 6 <= n <= 9:
        lit[4] = "purple"
        lit[n - 6] = "purple"
    elif n == 10:
        lit[4] = "blue"
    elif 11 <= n <= 14:
        lit[4] = "blue"
        lit[n - 11] = "purple"
    elif n == 15:
        lit[4] = "red"
    elif n == 16:
        lit[4] = "red"
        lit[0] = "purple"
    return lit


def led_words(n):
    """'LED 5 blue, LED 2 purple' — for a title attribute and screen readers."""
    parts = [f"LED {i} {c}" for i, c in enumerate(leds(n), 1) if c != "off"]
    return ", ".join(parts) if parts else "no LEDs lit"


def led_html(n):
    """The five status LEDs as they look on the device for mode n.

    Each lit dot carries its colour as a class (printed in colour) and the
    colour's initial as text, so the pattern survives a mono printer. The
    words are visually hidden but read out and shown on hover.
    """
    dots = "".join(
        f'<i class="{c}">{LED_LETTER[c]}</i>' if c != "off" else "<i></i>" for c in leds(n))
    words = led_words(n)
    return f'<span class="leds" title="{esc(words)}">{dots}<b>{esc(words)}</b></span>'


# The front photo is embedded as a data: URI because the card is a single standalone
# HTML file served straight from the API — there is no bundler and no second request.
# `assets/front.webp` is `images/front.png` cropped to its opaque bounds and resized
# to 700px; that is ~85 KB, and a headless-Chrome print check confirms Chrome
# rasterises a data-URI WebP into the PDF rather than dropping it.
_FRONT_B64 = None


def front_photo_uri():
    global _FRONT_B64
    if _FRONT_B64 is None:
        import base64
        from importlib.resources import files
        # package data: works installed, editable and PyInstaller-frozen alike
        data = files("qsprofile").joinpath("assets", "front.webp").read_bytes()
        _FRONT_B64 = "data:image/webp;base64," + base64.b64encode(data).decode("ascii")
    return _FRONT_B64


# Anchor points as percentages of the photo box. These are the same numbers the
# on-screen device view uses (web/src/device/layout.ts) measured off the same
# image, so the printed card and the screen point at the same holes. `lift` fans
# the three hole labels out vertically, in label-heights, so they cannot collide.
FRONT_HOLES = [
    ("Left", 33, 75, 6),
    ("Center", 47, 75, 9),
    ("Right", 61, 75, 6),
]
FRONT_PARTS = [
    ("Side tube", 82, 75, "right", "changes mode"),
    ("__LIP__", 47, 90, "below", "press with lip or chin"),
    ("Joystick", 33, 45, "left", "move the whole head"),
    ("Status LEDs", 50, 17, "above", "which mode is on"),
]


def mouthpiece_photo(lip_label):
    """The front of the device, with a labelled dot on each part."""
    h = [f'<figure class="mp"><img src="{front_photo_uri()}" alt="The front of the '
         f'QuadStick: the three mouthpiece holes, the side tube, the {esc(lip_label)} '
         f'and the joystick">']
    for label, x, y, lift in FRONT_HOLES:
        h.append(f'<span class="co above" style="left:{x}%;top:{y}%;--lift:{lift * 1.5}em">'
                 f'<i></i><b>{esc(label)}</b></span>')
    for label, x, y, side, note in FRONT_PARTS:
        text = lip_label if label == "__LIP__" else label
        # The status LEDs are drawn in their real colours everywhere else on the
        # card (purple for most modes; see leds()). Pointing at them with a
        # green dot would claim they were a colour they are not, so the callout
        # dot is LED purple.
        cls = " led" if label == "Status LEDs" else ""
        h.append(f'<span class="co {side}{cls}" style="left:{x}%;top:{y}%;--lift:0em">'
                 f'<i></i><b>{esc(text)}<small>{esc(note)}</small></b></span>')
    h.append("</figure>")
    return "".join(h)


CSS = """
@page { size: A4 portrait; margin: 14mm 12mm; }
:root { --ink:#1d1d1b; --paper:#fff; --line:#cfcfc9;
        --sip:#0b6e7a; --sip-soft:#e6f2f4; --puff:#ad4908; --puff-soft:#fbeadf;
        --mode:#1f4fbf;
        /* The device's status LEDs, as they actually light (see leds()). */
        --led-purple:#7a2bd6; --led-blue:#1f4fbf; --led-red:#d0281e;
        /* Callout markers on the device photo. The QuadStick is black, so the
           dots and leader lines need a colour that survives against it — acid
           green does, where --mode disappeared. Matches web/src/styles/tokens.css:
           the card and the screen have to look like the same thing. */
        --callout:#6fe600; --callout-edge:#3c7d00; }
* { box-sizing:border-box; }
body { font-family:"Atkinson Hyperlegible", "Helvetica Neue", Arial, sans-serif;
       color:var(--ink); background:#e9e9e6; margin:0; font-size:12.5px; line-height:1.35; }
.page { background:var(--paper); width:210mm; min-height:297mm; margin:10mm auto; padding:14mm 12mm; }
@media print { body{background:#fff} .page{margin:0; width:auto; min-height:0; padding:0; page-break-after:always} .noprint{display:none !important} }
h1 { font-size:30px; margin:0 0 4px; letter-spacing:-0.01em; }
h1 small { font-size:15px; font-weight:400; color:#555; display:block; margin-top:2px; }
h2 { font-size:15px; margin:22px 0 8px; }
.facts { display:flex; gap:24px; flex-wrap:wrap; margin:10px 0 18px; padding:10px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
.facts div b { display:block; font-size:11px; color:#555; font-weight:600; }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start; }
/* the front photo and its callouts */
.mp { position:relative; margin:0 0 6px; width:100%; }
.mp img { display:block; width:100%; }
.co { position:absolute; font-size:11px; line-height:1.15; }
/* the device is black, so a dot needs a light ring to be visible on it */
.co i { position:absolute; left:-4px; top:-4px; width:8px; height:8px; border-radius:50%;
        background:var(--callout); border:1.5px solid #fff; box-shadow:0 0 0 1px var(--callout-edge); }
/* and the text needs a paper-coloured plate: black-on-black is unreadable, and a
   printed card has to survive being read across a room */
.co b { position:absolute; white-space:nowrap; font-weight:700; background:rgba(255,255,255,.92);
        padding:1px 4px; border-radius:3px; }
.co b small { display:block; font-weight:400; color:#555; font-size:9.5px; }
/* the status-LED callout is LED purple, not callout green; see mouthpiece_photo() */
.co.led i { background:var(--led-purple); box-shadow:0 0 0 1px rgba(0,0,0,.35); }
.co.led::before { background:var(--led-purple); }
/* a leader line joins a lifted label back down to its dot */
.co.above b { left:50%; transform:translateX(-50%); bottom:calc(5px + var(--lift, 0em)); text-align:center; }
.co.above::before { content:""; position:absolute; left:0; bottom:3px; width:2px;
                    height:var(--lift, 0em); background:var(--callout); }
.co.below b { left:50%; transform:translateX(-50%); top:9px; text-align:center; }
.co.below::before { content:""; position:absolute; left:0; top:3px; width:2px; height:6px; background:var(--callout); }
.co.left b { right:12px; top:-0.7em; text-align:right; }
.co.right b { left:12px; top:-0.7em; }
.co.left::before, .co.right::before { content:""; position:absolute; top:0; width:10px; height:2px; background:var(--callout); }
.co.left::before { right:1px; } .co.right::before { left:1px; }
ol.modes { list-style:none; padding:0; margin:0; }
ol.modes li { display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid var(--line); }
.num { width:30px; height:30px; border-radius:50%; background:var(--mode); color:#fff; font-weight:700; display:inline-flex; align-items:center; justify-content:center; font-size:15px; flex:none; }
/* The five status LEDs. A lit dot is filled in its real colour and carries the
   colour's initial (P/B/R) so a mono print still tells purple, blue and red
   apart. print-color-adjust keeps the fill when the browser would otherwise
   drop backgrounds on paper. */
.leds { display:inline-flex; gap:3px; margin-left:auto; position:relative; }
.leds i { width:11px; height:11px; border-radius:50%; border:1px solid var(--ink); background:#fff;
          display:inline-flex; align-items:center; justify-content:center; font-style:normal;
          font-weight:700; font-size:7px; line-height:1; color:#fff;
          -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.leds i.purple { background:var(--led-purple); border-color:var(--led-purple); }
.leds i.blue { background:var(--led-blue); border-color:var(--led-blue); }
.leds i.red { background:var(--led-red); border-color:var(--led-red); }
/* the words are for screen readers; the dots are what prints */
.leds b { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
.switch li { margin:3px 0; }
.legend { display:flex; gap:14px; margin-top:8px; font-size:11.5px; color:#444; }
.legend span::before { content:""; display:inline-block; width:11px; height:11px; margin-right:5px; vertical-align:-1px; border-radius:2px; }
.legend .s::before{background:var(--sip)} .legend .p::before{background:var(--puff)}
/* mode page */
.modehead { display:flex; align-items:baseline; gap:14px; margin-bottom:12px; }
.modehead .num { width:44px; height:44px; font-size:22px; align-self:center; }
.modehead h1 { margin:0; }
.modehead .leds { margin-left:auto; align-self:center; }
.modehead .leds i { width:15px; height:15px; font-size:9px; }
table.grid { border-collapse:collapse; width:100%; table-layout:fixed; }
table.grid th, table.grid td { border:1px solid var(--line); vertical-align:top; padding:5px; }
table.grid thead th { font-size:12px; font-weight:600; background:#f4f4f1; }
table.grid tbody th { text-align:left; width:70px; font-size:12.5px; }
tr.sip th { color:var(--sip); } tr.puff th { color:var(--puff); }
tr.soft td { background:#fafaf8; }
tr.sip.soft th, tr.puff.soft th { font-weight:500; }
td:empty { background:repeating-linear-gradient(45deg,#fff 0 6px,#f5f5f2 6px 7px); }
.chip { margin:2px 0; padding:3px 4px; border-radius:5px; border:1px solid var(--line); background:#fff; }
.chip .glyph { display:inline-block; font-weight:700; font-size:14px; min-width:22px; }
.chip .act { display:block; font-size:11.5px; color:#333; }
/* the owner's own Note for this row, under the game action it belongs to */
.chip .act-note { display:block; font-size:10.5px; color:#555; font-style:italic; }
.chip .fn.seq { background:var(--mode); }
.chip .fn { white-space:nowrap; display:inline-block; font-size:10px; color:#fff; background:var(--ink); border-radius:3px; padding:1px 4px; margin-left:4px; vertical-align:2px; }
.chip.system .glyph { color:var(--mode); }
tr.sip .chip { border-left:4px solid var(--sip); } tr.puff .chip { border-left:4px solid var(--puff); }
.strip { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
.strip h2 { margin-top:0; }
.strip ul { margin:0; padding-left:18px; }
.strip .chip { display:inline-block; vertical-align:middle; }
.lip { display:flex; align-items:center; gap:10px; }
.lip .lbl { font-weight:600; }
.free { margin-top:14px; font-size:11px; color:#666; }
.free code { background:#f4f4f1; padding:1px 4px; border-radius:3px; margin-right:4px; white-space:nowrap; }
.note { font-size:11.5px; color:#555; margin-top:6px; }
ul.note { padding-left:16px; margin:6px 0 0; }
ul.note li { margin:1px 0; }
/* print bar and checks: screen only */
.printbar { position:sticky; top:0; z-index:5; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
            padding:10px 14px; background:#fff; border-bottom:1px solid var(--line); font-size:13px; }
.printbar button { min-height:40px; padding:0 16px; border:1px solid var(--mode); border-radius:8px;
                   background:var(--mode); color:#fff; font:inherit; font-weight:700; cursor:pointer; }
.printbar button:hover { background:#1a43a4; }
.printbar span { color:#555; }
.checks { font-size:13px; }
.checks li { margin:6px 0; padding-left:8px; border-left:4px solid var(--line); }

/* ---- summary sheet: four columns, big type, one page if it fits ---- */
.summary h1 { margin-bottom:10px; }
table.sum { border-collapse:collapse; width:100%; table-layout:fixed; margin-bottom:18px; }
table.sum col.a { width:28%; } table.sum col.b { width:30%; } table.sum col.c { width:18%; }
table.sum col.d { width:24%; }
table.sum thead th { font-size:14px; text-align:left; padding:7px 8px; background:var(--ink); color:#fff;
                     border:1px solid var(--ink); }
table.sum td { border:1px solid var(--line); padding:6px 8px; font-size:13.5px; vertical-align:top; }
table.sum tbody tr:nth-child(even) td { background:#f7f7f4; }
table.sum td.qs { font-weight:600; }
table.sum td.qs.sip { color:var(--sip); } table.sum td.qs.puff { color:var(--puff); }
table.sum td.out { font-weight:700; font-size:15px; }
table.sum td.note { color:#555; font-size:12px; }
table.sum td .fn { margin-left:0; }
table.sum td small { display:block; font-weight:400; color:#555; font-size:11px; }
.modebar { display:flex; align-items:center; gap:10px; margin:18px 0 8px; page-break-after:avoid; }
.modebar .num { width:26px; height:26px; font-size:13px; }
.modebar h2 { margin:0; font-size:16px; }
.modebar h2 small { font-weight:400; color:#555; font-size:12px; }
.modebar .leds { margin-left:auto; }
@media print { table.sum { page-break-inside:auto; } table.sum tr { page-break-inside:avoid; } }
/* ---- overview sheet: every command once, mode dots in column 1 ----
   Tighter than the per-mode tables on purpose: this sheet only earns its place
   if the whole profile lands on one page, and ~54 rows at the normal 13.5px
   spills onto a second. Measured against fixtures/ddfortnite.csv (54 rows) and
   fixtures/cod.csv (49) with headless Chrome at A4. */
.overview h1 { margin-bottom:4px; }
.overview .lead { margin:0 0 7px; font-size:10.5px; color:#555; max-width:62em; }
table.sum.ov { margin-bottom:8px; }
table.sum.ov thead th { font-size:11px; padding:3px 6px; }
table.sum.ov td { padding:1px 6px; font-size:10.5px; line-height:1.2; }
table.sum.ov td.out { font-size:11px; }
table.sum.ov td.note { font-size:10px; }
table.sum.ov td.dots { padding:1px 6px; }
table.sum.ov td .fn { font-size:9px; margin-left:4px; }
table.sum.ov col.a { width:25%; } table.sum.ov col.b { width:26%; }
table.sum.ov col.m { width:11%; } table.sum.ov col.c { width:16%; }
table.sum.ov col.d { width:22%; }
table.sum td.dots { padding:6px; }
.modedots { display:flex; flex-wrap:wrap; gap:3px; align-items:center; }
.modedots i { width:6px; height:6px; border-radius:50%; border:1px solid var(--ink); background:#fff;
              flex:none; }
/* lit in LED purple: on the device a mode's light is purple, and the strip reads as
   'which lights' for modes 1-5, so the UI blue looked like the wrong answer */
.modedots i.on { background:var(--led-purple); border-color:var(--led-purple); }
/* The words are for screen readers and for anyone who cannot pick the dots apart;
   they are not printed, the dots are. */
.modedots b { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
/* mode-change rows: two dots and an arrow, never the full strip */
.modedots.step { flex-wrap:nowrap; gap:2px; }
.modedots.step .ar { font-size:9px; line-height:1; color:var(--ink); flex:none; }
.checks li.error { border-color:#c0261d; } .checks li.warning { border-color:var(--puff); } .checks li.info { border-color:#999; color:#555; }
"""


# ------------------------------------------------------------------ summary sheet
def console_heading(cfg):
    """Column 3's heading: what the console calls the button."""
    return "Xbox" if cfg.console == "xbox" else "PS5"


def qs_cell(m):
    """Column 2: what you do on the QuadStick, in plain words."""
    parts = [input_label(i) for i in m.inputs]
    txt = esc(" then ".join(parts))
    cls = "qs"
    first = classify_input(m.inputs[-1]) or {}
    if first.get("action") == "sip":
        cls += " sip"
    elif first.get("action") == "puff":
        cls += " puff"
    return f'<td class="{cls}">{txt}{fn_tag(m)}</td>'


def out_cell(m, console):
    """Column 3: the console button this produces."""
    label = glyphs(console).get(m.output) or output_label(m.output) or m.output
    return f'<td class="out">{esc(label)}</td>'


def note_cell(m):
    """Column 4: the row's own note — what this actually does in the game.

    The note is the editor's Note column (`Mapping.comment`). It never reaches the
    device file; it exists so the printed sheet can say "Aim" next to L2.
    """
    return f'<td class="note">{esc(m.comment or "")}</td>'


def summary_rows(mode, actions, console):
    """One row per active mapping, named actions first, then the rest.

    Sorting by whether the row has a game action keeps the lines the player actually
    looks up ("Jump", "Reload") at the top of each mode's table.
    """
    rows = []
    for m in mode.active():
        act = action_for(actions, mode, m.output)
        rows.append((0 if act else 1, act.lower(), act, m))
    rows.sort(key=lambda r: (r[0], r[1]))
    out = []
    for _, _, act, m in rows:
        label = esc(act) if act else f'<span style="color:#777">{esc(output_label(m.output) or m.output)}</span>'
        out.append(f"<tr><td>{label}</td>{qs_cell(m)}{out_cell(m, console)}{note_cell(m)}</tr>")
    return "".join(out)


def mode_dots(numbers, total, output=""):
    """One dot per mode in the profile, lit for each mode in `numbers`.

    Not the same thing as `leds()`: that draws the five physical status LEDs on
    the device, this is a "which modes is this command in" strip for the overview
    table. Up to MAX_MODES dots have to fit a narrow column, so they wrap.

    Mode-change rows get an arrow instead. Dots would be actively misleading
    there: the row doesn't *live* in those modes, it moves you between them, and
    a strip of lit dots reads as "works in modes 1-5" rather than "steps you on
    by one". The direction follows the output keyword.
    """
    if output in MODE_CHANGE_OUTPUTS:
        back = output == "decrement_mode"
        arrow = ('<i></i><span class="ar">&larr;</span><i class="on"></i>' if back
                 else '<i class="on"></i><span class="ar">&rarr;</span><i></i>')
        words = {"increment_mode": "Steps to the next mode",
                 "decrement_mode": "Steps to the previous mode"}.get(output, "Loads another profile")
        return f'<span class="modedots step" title="{esc(words)}">{arrow}<b>{esc(words)}</b></span>'
    lit = set(numbers)
    dots = "".join(f'<i class="{"on" if i in lit else ""}"></i>' for i in range(1, total + 1))
    words = "Modes " + ", ".join(str(n) for n in sorted(lit)) if len(lit) > 1 else f"Mode {min(lit)}"
    return f'<span class="modedots" title="{esc(words)}">{dots}<b>{esc(words)}</b></span>'


def overview_rows(cfg, actions):
    """Every distinct command in the profile, once, with the modes it belongs to.

    Two rows collapse when they fire on the same input(s), drive the same output
    with the same function and params, *and* mean the same thing in the game —
    same action name and same note. That last part matters: `actions["modes"]`
    can give one physical row a different name per mode, and the note is written
    per row, so rows that would print differently must stay separate lines.

    The identity tuple is exactly what qs_cell/out_cell/fn_tag render from, so
    anything that collapses is guaranteed to have printed identically before.
    """
    groups = {}
    for mode in cfg.modes:
        for m in mode.active():
            act = action_for(actions, mode, m.output)
            key = (tuple(m.inputs), m.output, m.function, tuple(m.params), act, m.comment)
            if key not in groups:
                groups[key] = {"m": m, "act": act, "modes": []}
            groups[key]["modes"].append(mode.number)

    total = len(cfg.modes)
    # First mode wins the ordering, so the page reads "all of mode 1, then what
    # mode 2 adds, ..." — and named actions come before unnamed ones inside each.
    items = sorted(groups.values(),
                   key=lambda d: (d["modes"][0], 0 if d["act"] else 1, d["act"].lower(),
                                  " ".join(d["m"].inputs)))
    out = []
    for d in items:
        m, act = d["m"], d["act"]
        label = esc(act) if act else f'<span style="color:#777">{esc(output_label(m.output) or m.output)}</span>'
        out.append(f'<tr><td>{label}</td>{qs_cell(m)}'
                   f'<td class="dots">{mode_dots(d["modes"], total, m.output)}</td>'
                   f'{out_cell(m, cfg.console)}{note_cell(m)}</tr>')
    return "".join(out)


def render_overview(cfg, actions):
    """Page 1 of the summary: the whole profile on one sheet, nothing repeated."""
    game = actions.get("game", "")
    body = overview_rows(cfg, actions)
    if not body:
        return ""
    head = console_heading(cfg)
    return ('<section class="page summary overview">'
            f'<h1>{esc(game or cfg.name)} <small>every command, once — {esc(cfg.filename)}</small></h1>'
            '<p class="lead">Every command once. In the Mode column a filled dot means the command '
            'works in that mode; an arrow means the command changes mode. '
            'The per-mode tables follow.</p>'
            '<table class="sum ov"><colgroup><col class="a"><col class="b"><col class="m"><col class="c">'
            '<col class="d"></colgroup>'
            f'<thead><tr><th>{esc(game or "Game")}</th><th>QuadStick</th><th>Mode</th>'
            f'<th>{esc(head)}</th><th>Note</th></tr></thead>'
            f'<tbody>{body}</tbody></table>'
            '<div class="legend"><span class="s">Sip = draw air in</span>'
            '<span class="p">Puff = blow out</span></div>'
            '</section>')


def render_summary(cfg, actions):
    """A compact cheat-sheet: game action | QuadStick | console button.

    Page 1 is the overview — every distinct command once, with mode dots — and
    the per-mode tables follow. Deliberately not the reference card: no diagram,
    no grid, no checks. Meant to be printed once and taped next to the monitor.
    """
    game = actions.get("game", "")
    head = console_heading(cfg)
    p = [render_overview(cfg, actions),
         '<section class="page summary">',
         f'<h1>{esc(game or cfg.name)} <small>QuadStick summary — {esc(cfg.filename)}</small></h1>']
    for mode in cfg.modes:
        body = summary_rows(mode, actions, cfg.console)
        if not body:
            continue
        # mode.label often just repeats the name; only show it when it adds something
        sub = (f' <small>{esc(mode.label)}</small>'
               if mode.label and mode.label.strip().lower() != mode.name.strip().lower() else '')
        p.append(f'<div class="modebar"><span class="num">{mode.number}</span>'
                 f'<h2>{esc(mode.name)}{sub}</h2>{led_html(mode.number)}</div>')
        p.append('<table class="sum"><colgroup><col class="a"><col class="b"><col class="c">'
                 '<col class="d"></colgroup>'
                 f'<thead><tr><th>{esc(game or "Game")}</th><th>QuadStick</th><th>{esc(head)}</th>'
                 '<th>Note</th></tr></thead>'
                 f'<tbody>{body}</tbody></table>')
    p.append('<div class="legend"><span class="s">Sip = draw air in</span>'
             '<span class="p">Puff = blow out</span></div>')
    p.append('</section>')
    bar = ('<div class="printbar noprint">'
           '<button type="button" onclick="window.print()">Print this summary</button>'
           '<span>Page 1 lists every command once, with dots for the modes it works in; '
           'then one compact table per mode. For the diagram and the full grid, '
           'print the detailed sheets instead.</span></div>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>{esc(game or cfg.name)} QuadStick summary</title>'
            f'<style>{CSS}</style></head><body>' + bar + "".join(p) + '</body></html>')


def render(cfg, actions, findings):
    game = actions.get("game", "")
    console = cfg.console
    pages = []
    # ---------------------------------------------------------- page 1
    p = [f'<section class="page">',
         f'<h1>{esc(game or cfg.name)} <small>QuadStick profile reference — {esc(cfg.filename)}</small></h1>',
         '<div class="facts">',
         f'<div><b>Modes</b>{len(cfg.modes)}</div>',
         f'<div><b>Console names</b>{"Xbox" if cfg.console == "xbox" else "PlayStation"}</div>',
         f'<div><b>Output</b>{esc(cfg.modes[0].channel.upper() if cfg.modes else "")}</div>',
         '</div>',
         '<div class="cols"><div>', mouthpiece_photo(input_name(actions, "lip", "Lip button")),
         '<div class="legend"><span class="s">Sip = draw air in</span><span class="p">Puff = blow out</span></div>',
         '<p class="note">A soft sip or puff is gentle — the QuadStick beeps. A hard one is firm — it clicks. '
         'Left + Center means sip or puff on both holes at once.</p>',
         '</div><div>',
         '<h2>Modes in this profile</h2><ol class="modes">']
    for m in cfg.modes:
        p.append(f'<li>{"".join(["<span class=num>", str(m.number), "</span>"])}<span>{esc(m.name)}'
                 f'<br><small style="color:#555">{esc(m.label)}</small></span>{led_html(m.number)}</li>')
    p.append('</ol><p class="note">The five lights show which mode is active. Modes 1–5 light one '
             'purple light; 6–9 keep light 5 purple and add one more. From mode 10 light 5 turns '
             'blue (alone for 10, with one purple light for 11–14), and red for 15 and 16. '
             'The letter in each dot is its colour: P purple, B blue, R red.</p>')
    p.append('<h2>Changing mode</h2><ul class="switch">')
    p.extend(f"<li>{l}</li>" for l in switching(cfg))
    p.append('</ul><p class="note">To change to a different profile file: long hard sip on the side tube, '
             'move the joystick until the lights show the file you want, then press the lip.</p>')
    p.append('</div></div></section>')
    pages.append("".join(p))
    # ---------------------------------------------------------- mode pages
    for mode in cfg.modes:
        switches = switches_summary(mode, actions, console)
        p = ['<section class="page">',
             f'<div class="modehead"><span class="num">{mode.number}</span><h1>{esc(mode.name)}'
             f'<small>{esc(game)} — {esc(mode.label)}</small></h1>{led_html(mode.number)}</div>',
             tube_grid(mode, actions, console),
             '<div class="strip"><div><h2>Joystick</h2><ul>', joystick_summary(mode, actions, console), '</ul></div>',
             f'<div><h2>{esc(input_name(actions, "lip", "Lip button"))}</h2>',
             lip_summary(mode, actions, console) or '<p class="note">Not used in this mode</p>',
             (('<h2>Switches</h2>' + switches) if switches else ''),
             '</div></div>']
        ov = overrides_summary(mode)
        if ov:
            p.append(ov)
        # Notes now ride on the chip for the row they belong to (tube grid, lip,
        # switches). What is left over is a note on a stick or D-pad row, which
        # joystick_summary writes as prose rather than as a chip — so those still
        # need somewhere to go, one per line and named by their button.
        chipped = chipped_inputs(mode)
        leftover = [m for m in mode.active()
                    if m.comment and m.inputs and m.inputs[-1] not in chipped]
        if leftover:
            p.append('<ul class="note">' + "".join(
                f'<li><b>{esc(output_label(m.output) or m.output)}</b> — {esc(m.comment)}</li>'
                for m in leftover) + '</ul>')
        free = unused_inputs(mode)
        if free:
            p.append('<p class="free">Free inputs in this mode: ' +
                     " ".join(f"<code>{esc(f)}</code>" for f in free) + '</p>')
        p.append('</section>')
        pages.append("".join(p))
    # ---------------------------------------------------------- checks (screen only)
    p = ['<section class="page noprint"><h1>Checks <small>what the profile builder would flag before export</small></h1><ul class="checks">']
    for sev, mode, row, msg in findings:
        where = " ".join(x for x in [f"Mode {mode}" if mode else "", f"row {row}" if row else ""] if x)
        p.append(f'<li class="{sev}"><b>{sev.title()}</b>{(" · " + where) if where else ""}: {esc(msg)}</li>')
    if not findings:
        p.append("<li>No problems found.</li>")
    p.append('</ul></section>')
    pages.append("".join(p))
    # The print bar is screen-only: it saves hunting through the browser menu, and
    # the browser's own print-to-PDF is why this card needs no PDF service.
    bar = ('<div class="printbar noprint">'
           '<button type="button" onclick="window.print()">Print this card</button>'
           f'<span>{len(cfg.modes)} mode pages on A4. '
           'Your browser\'s print dialog can also save it as a PDF.</span>'
           '</div>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>{esc(game or cfg.name)} QuadStick reference</title>'
            f'<style>{CSS}</style></head><body>'
            + bar + "".join(pages) + "</body></html>")


def main():
    import sys
    from .parser import load
    from .validate import validate
    src = sys.argv[1]
    actions = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
    out = sys.argv[3] if len(sys.argv) > 3 else "reference.html"
    cfg, problems = load(src)
    findings = validate(cfg, problems)
    open(out, "w").write(render(cfg, actions, findings))
    errs = sum(1 for f in findings if f[0] == "error")
    print(f"{cfg.filename}: {len(cfg.modes)} modes, {errs} errors, "
          f"{sum(1 for f in findings if f[0]=='warning')} warnings -> {out}")


if __name__ == "__main__":
    main()
