"""N11: the CLI is the handover path for anyone without the web app, so a missing
argument or a mistyped console must be a usage message, not a traceback, and the
card must be written as UTF-8 whatever the machine's locale (it contains → and –)."""
import json
import pathlib
import pytest
from qsprofile import load
from qsprofile.cli import main

FX = pathlib.Path(__file__).parent.parent / "fixtures"
ACTIONS = pathlib.Path(__file__).parent.parent / "actions" / "actions_fortnite.json"


# ---------------------------------------------------------------- check
def test_check_lists_findings_and_exits_zero_without_errors(capsys):
    assert main(["check", str(FX / "ddfortnite.xlsx")]) == 0        # warnings, no errors
    out = capsys.readouterr().out
    assert "warning" in out
    assert "mode " in out


# ---------------------------------------------------------------- card
def test_card_is_written_as_utf8(tmp_path, capsys):
    out = tmp_path / "card.html"
    assert main(["card", str(FX / "ddfortnite.csv"), str(ACTIONS), str(out)]) == 0
    assert b"\xe2\x86\x92" in out.read_bytes()            # → survived, so it is UTF-8
    assert "QuadStick" in out.read_text(encoding="utf-8")
    assert f"wrote {out}" in capsys.readouterr().out


def test_card_reports_an_unreadable_actions_file_instead_of_raising(tmp_path, capsys):
    bad = tmp_path / "actions.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert main(["card", str(FX / "ddfortnite.csv"), str(bad), str(tmp_path / "c.html")]) == 1
    assert "could not read" in capsys.readouterr().err


# ---------------------------------------------------------------- convert
def test_convert_writes_the_target_console(tmp_path, capsys):
    out = tmp_path / "ps.csv"
    src = FX / "Call_of_Duty_Advanced_Warfare_XBox_One.xlsx"
    assert main(["convert", str(src), "playstation", str(out), "codawps.csv"]) == 0
    assert "xbox -> playstation" in capsys.readouterr().out
    cfg, _ = load(str(out))
    assert cfg.console == "playstation" and cfg.filename == "codawps.csv"


def test_convert_rejects_an_unknown_console(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["convert", str(FX / "ddfortnite.csv"), "xbx", str(tmp_path / "o.csv")])
    assert e.value.code == 2


def test_convert_rejects_an_output_that_is_neither_csv_nor_xlsx(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["convert", str(FX / "ddfortnite.csv"), "xbox", str(tmp_path / "o.txt")])
    assert e.value.code == 2


# ---------------------------------------------------------------- usage
@pytest.mark.parametrize("argv", [[], ["card"], ["check"], ["nonsense"],
                                  ["convert", "a.csv", "xbox"]])
def test_missing_or_unknown_arguments_are_a_usage_error(argv):
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 2


def test_an_unreadable_profile_is_a_message_not_a_traceback(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope.csv")]) == 1
    assert "could not read" in capsys.readouterr().err


def test_empty_argv_does_not_fall_through_to_sys_argv(monkeypatch):
    """`main([])` must mean "no arguments", not "read sys.argv" — the old
    `argv or sys.argv[1:]` made an explicit empty list silently pick up whatever
    pytest was invoked with."""
    monkeypatch.setattr("sys.argv", ["qsprofile", "check", str(FX / "ddfortnite.csv")])
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_check_and_convert_both_stop_on_an_error(tmp_path, capsys):
    """Export is refused while errors exist; `check` says 1 so a script can tell."""
    src = tmp_path / "bad.csv"
    src.write_bytes(b"QuadStick Configuration,Version 1.4,,Bad\r\n"
                    b"Profile Name,,Left joy,\r\n"
                    b"bad.csv,,Normal,\r\n"
                    b"Output or Function,Function,usb,\r\n"
                    b"not_an_output,normal,lip,\r\n"
                    b"\r\n")
    assert main(["check", str(src)]) == 1
    assert "error" in capsys.readouterr().out
    assert main(["convert", str(src), "xbox", str(tmp_path / "o.csv")]) == 1
    assert "refusing to convert" in capsys.readouterr().err
