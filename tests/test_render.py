"""The printable card: what it says about the device must match the firmware."""
import pathlib
import pytest
from qsprofile.render import leds, led_html, led_words, LED_COLOURS

FX = pathlib.Path(__file__).parent.parent / "fixtures"

# Straight from the firmware's update_active_config_leds: one entry per LED 1..5.
FIRMWARE_LEDS = {
    1: ["purple", "off", "off", "off", "off"],
    2: ["off", "purple", "off", "off", "off"],
    3: ["off", "off", "purple", "off", "off"],
    4: ["off", "off", "off", "purple", "off"],
    5: ["off", "off", "off", "off", "purple"],
    6: ["purple", "off", "off", "off", "purple"],
    7: ["off", "purple", "off", "off", "purple"],
    8: ["off", "off", "purple", "off", "purple"],
    9: ["off", "off", "off", "purple", "purple"],
    10: ["off", "off", "off", "off", "blue"],
    11: ["purple", "off", "off", "off", "blue"],
    12: ["off", "purple", "off", "off", "blue"],
    13: ["off", "off", "purple", "off", "blue"],
    14: ["off", "off", "off", "purple", "blue"],
    15: ["off", "off", "off", "off", "red"],
    16: ["purple", "off", "off", "off", "red"],
}


@pytest.mark.parametrize("n", range(1, 17))
def test_led_pattern_matches_firmware_for_1_to_16(n):
    got = leds(n)
    assert got == FIRMWARE_LEDS[n]
    assert all(c in LED_COLOURS for c in got)


def test_every_mode_1_to_16_has_a_distinct_led_pattern():
    """Colour is part of the encoding: with it, no two modes look alike."""
    seen = [tuple(leds(n)) for n in range(1, 17)]
    assert len(set(seen)) == 16


def test_led_html_prints_colour_and_a_letter_for_mono_printers():
    h = led_html(11)
    assert h.count("<i") == 5
    assert '<i class="purple">P</i>' in h
    assert '<i class="blue">B</i>' in h
    assert "red" not in h
    # the words are there for screen readers and the hover title
    assert led_words(11) == "LED 1 purple, LED 5 blue"
    assert 'title="LED 1 purple, LED 5 blue"' in h
    assert led_html(16).count("<i></i>") == 3
    assert '<i class="red">R</i>' in led_html(16)


def test_zero_mode_card_returns_html():
    """A profile with no modes yet (a fresh one in the editor) still gets a card."""
    from qsprofile import Config, render, render_summary
    cfg = Config(name="Empty", filename="empty.csv", modes=[])
    card = render(cfg, {}, [])
    assert card.startswith("<!doctype html>") and card.endswith("</html>")
    assert "Empty" in card and "0 mode pages" in card
    summary = render_summary(cfg, {})
    assert summary.startswith("<!doctype html>") and summary.endswith("</html>")


def test_summary_prints_the_note_as_a_fourth_column():
    """The editor's Note column is the point of the printed sheet for the owner:
    "L2" means nothing, "Aim" does. It prints on both the overview and the
    per-mode tables, and is escaped like every other cell."""
    from qsprofile import load, render_summary
    cfg, _ = load(str(FX / "ddfortnite.csv"))
    for mode in cfg.modes:
        for m in mode.active():
            if m.output == "left_2":
                m.comment = "Aim <down>"
    h = render_summary(cfg, {})
    assert "<th>Note</th>" in h
    assert '<td class="note">Aim &lt;down&gt;</td>' in h
    assert "<down>" not in h
    # the overview header gained a column too, not just the per-mode tables
    assert '<th>PS5</th><th>Note</th>' in h


def test_detailed_sheet_prints_each_note_on_its_own_button():
    """The Note belongs to one row, so it prints on that row's chip.

    It used to be stripped off every row in the mode and joined with spaces into
    one paragraph at the foot of the page, which read as a run-on sentence
    ("Resupply from teamate Med tactical e.g Flashbang Aim ...") and left the
    buttons themselves unlabelled.
    """
    from qsprofile import load, render
    cfg, _ = load(str(FX / "ddfortnite.csv"))
    notes = {}
    for mode in cfg.modes:
        for m in mode.active():
            if m.inputs and m.inputs[-1].startswith("mp_"):
                notes[m.output] = m.comment = f"note for {m.output}"
    assert len(notes) > 1, "fixture must map more than one mouthpiece row"
    h = render(cfg, {}, [])
    for note in notes.values():
        assert f'<span class="act-note">{note}</span>' in h
    # each note sits inside the chip for its own button, not in one lump
    assert " ".join(notes.values()) not in h


def test_detailed_sheet_note_survives_when_the_row_has_no_game_action():
    """A note with no action behind it is the only label that button will get."""
    from qsprofile import load, render
    cfg, _ = load(str(FX / "ddfortnite.csv"))
    target = None
    for mode in cfg.modes:
        for m in mode.active():
            if m.inputs and m.inputs[-1].startswith("mp_"):
                target = m
                m.comment = "Resupply <from> teamate"
                break
        if target:
            break
    h = render(cfg, {}, [])            # no actions file at all, so no action text
    assert '<span class="act-note">Resupply &lt;from&gt; teamate</span>' in h
    assert "<from>" not in h
    # nothing renders an empty action line above it
    assert '<span class="act"></span>' not in h


def test_detailed_sheet_lists_a_note_the_chips_cannot_carry():
    """A stick or D-pad row is written as prose, not as a chip, so its note is
    listed separately — named by its button rather than run together."""
    from qsprofile import load, render
    from qsprofile.render import chipped_inputs
    cfg, _ = load(str(FX / "ddfortnite.csv"))
    found = None
    for mode in cfg.modes:
        chipped = chipped_inputs(mode)
        for m in mode.active():
            if m.inputs and m.inputs[-1] not in chipped:
                found = m
                m.comment = "only on the stick"
                break
        if found:
            break
    assert found is not None, "fixture must map a joystick or D-pad row"
    h = render(cfg, {}, [])
    assert '<ul class="note">' in h
    assert "only on the stick" in h


def test_overview_keeps_rows_with_different_notes_apart():
    """Rows that print differently must not collapse into one overview line.

    Same input, same output, same function — but a different note per mode, so
    two lines, each with its own note. Before the note column they were one row.
    """
    from qsprofile import load, render_summary
    cfg, _ = load(str(FX / "ddfortnite.csv"))
    seen = []
    for mode in cfg.modes:
        for m in mode.active():
            if m.output == "left_2":
                m.comment = f"Aim in mode {mode.number}"
                seen.append(m.comment)
    assert len(seen) > 1, "fixture must map left_2 in more than one mode"
    h = render_summary(cfg, {})
    for note in seen:
        assert f'<td class="note">{note}</td>' in h


def test_mode_change_rows_show_an_arrow_not_a_strip_of_dots():
    """"Next mode" doesn't live in modes 1-5, it steps you between them.

    A full lit strip would read as "works in every mode", which is the wrong
    idea, so those rows get a direction arrow instead.
    """
    from qsprofile.render import mode_dots
    nxt = mode_dots([1, 2, 3], 5, "increment_mode")
    prev = mode_dots([1, 2, 3], 5, "decrement_mode")
    assert "&rarr;" in nxt and "next mode" in nxt.lower()
    assert "&larr;" in prev and "previous mode" in prev.lower()
    # two dots and an arrow, never one dot per mode
    assert nxt.count("<i") == 2 and prev.count("<i") == 2
    # an ordinary row is unchanged: one dot per mode, lit where it works
    plain = mode_dots([1, 3], 5, "cross")
    assert plain.count("<i") == 5 and plain.count('class="on"') == 2
    assert "&rarr;" not in plain and "&larr;" not in plain


def test_console_naming_does_not_leak_between_renders():
    """Rendering a PlayStation card then an Xbox one (or the other way round)
    must give the same two cards: the console is the profile's, not the module's."""
    from qsprofile import load, convert, render, render_summary
    xbox, _ = load(str(FX / "Call_of_Duty_Advanced_Warfare_XBox_One.xlsx"))
    ps, _ = convert(xbox, "playstation")
    assert xbox.console == "xbox" and ps.console == "playstation"

    ps_first = render(ps, {}, [])
    xbox_after_ps = render(xbox, {}, [])
    xbox_first_summary = render_summary(xbox, {})
    ps_after_xbox = render(ps, {}, [])
    xbox_again = render(xbox, {}, [])
    ps_summary = render_summary(ps, {})

    assert ps_first == ps_after_xbox
    assert xbox_after_ps == xbox_again
    assert render_summary(xbox, {}) == xbox_first_summary
    # and each really is named for its own console
    assert "Console names</b>Xbox" in xbox_after_ps and "Console names</b>PlayStation" in ps_first
    assert ">LB<" in xbox_after_ps and ">LB<" not in ps_first
    assert ">L1<" in ps_first and ">L1<" not in xbox_after_ps
    assert "<th>Xbox</th>" in xbox_first_summary and "<th>PS5</th>" in ps_summary
