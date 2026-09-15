"""Build catalog rows from core/qsprofile/catalog.py — the single source of truth.
Nothing here is hand-typed vocabulary; everything is derived from the catalog module."""
from qsprofile import catalog as C


def input_rows():
    names = list(C.all_mouthpiece_inputs())
    names += [f"right_{a}{s}" for a in ("sip", "puff") for s in ("", "_soft")]
    names += ["lip", "lip_soft"]
    names += [f"{d}{r}" for d in C.JOY_DIRS + C.JOY_ZONES for r in ("", "_inner")] + ["center"]
    names += [f"digital_in_{n}" for n in range(1, 9)]
    names += [f"usb_{u}_{d}{r}" for u in (1, 2)
              for d in C.JOY_DIRS + C.JOY_ZONES + [f"button_{n}" for n in range(1, 16)]
              for r in ("", "_inner")]
    # older firmware input names: still accepted by 2373, so the FK must hold for a
    # profile that uses one. classify_input() marks them kind="legacy" and the
    # validator warns; they are sorted last so the UI never offers them first.
    names += list(C.LEGACY_INPUTS)
    rows = []
    for i, n in enumerate(names):
        info = C.classify_input(n)
        assert info, n
        rows.append(dict(name=n, kind=info["kind"], tube=info.get("tube"),
                         action=info.get("action") or info.get("dir"),
                         strength=info.get("strength") or info.get("ring"),
                         label=info["label"], jack=info.get("jack"), sort_order=i))
    return rows


def output_rows():
    """Every catalog output, the full kb_* / ir_* keyword lists included (they are
    part of OUTPUTS now, so nothing is seeded on top of the catalog)."""
    return [dict(name=n, grp=C.output_group(n), ps_glyph=C.PS_BUTTONS.get(n),
                 xbox_name=C.PS_TO_XBOX.get(n), xbox_glyph=C.XBOX_GLYPH.get(n),
                 label=label, sort_order=i)
            for i, (n, label) in enumerate(C.OUTPUTS.items())]


def function_rows():
    return [dict(name=n, max_params=mx, description=d, sort_order=i)
            for i, (n, (mx, d)) in enumerate(C.FUNCTIONS.items())]


def output_family_group(name):
    """Group for an output: static catalog first, then the kb_* / ir_* regex
    families (a keyword outside the lists is still valid; see bridge.ensure_output).
    None if the name is not an output at all."""
    if name in C.OUTPUTS:
        return C.output_group(name)
    if C._KB_RE.match(name):
        return "keyboard"
    if C._IR_RE.match(name):
        return "ir"
    return None
