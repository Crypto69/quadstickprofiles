"""write_xlsx must never hand openpyxl a sheet title Excel refuses: a mode name is
free text on the device (C1 label / tab name) but a tab name in Excel has rules."""
import pytest
from openpyxl import load_workbook
from qsprofile import load, write_xlsx
from qsprofile.model import Config, Mode, Mapping
from qsprofile.convert import sheet_title


def _cfg(names):
    cfg = Config(name="Titles", filename="titles.csv")
    for i, n in enumerate(names, start=1):
        cfg.modes.append(Mode(number=i, name=n, label=n, channel="usb",
                              mappings=[Mapping(row=4, output="cross", function="normal",
                                                params=[], inputs=["lip"])]))
    return cfg


def _titles(path):
    wb = load_workbook(path, read_only=True)
    try:
        return wb.sheetnames
    finally:
        wb.close()


def test_mode_names_excel_rejects_still_export(tmp_path):
    out = tmp_path / "t.xlsx"
    write_xlsx(_cfg(["A/B?", "[Aim]: fine*", "x" * 40, "Left joy", "left joy", "", "Preferences"]), str(out))
    assert _titles(out) == ["A-B-", "-Aim-- fine-", "x" * 31, "Left joy", "left joy 2",
                            "Mode 6", "Preferences 2", "Preferences"]
    cfg, problems = load(str(out))
    # the C1 label is what the device shows; it is the original text, untouched
    assert [m.label for m in cfg.modes] == ["A/B?", "[Aim]: fine*", "x" * 40, "Left joy", "left joy", "", "Preferences"]
    assert not [p for p in problems if p[0] == "error"], problems


def test_duplicate_suffix_stays_inside_31_characters():
    used = set()
    long = "y" * 31
    assert sheet_title(long, used, "Mode 1") == long
    second = sheet_title(long, used, "Mode 2")
    assert second == "y" * 29 + " 2" and len(second) == 31
    assert sheet_title(long, used, "Mode 3") == "y" * 29 + " 3"


def test_free_text_cells_are_never_formulas(tmp_path):
    """W5: comments round-trip through column K of the .xlsx, and a mode label, a
    filename or a preference override value are free text too. openpyxl types a str
    starting with '=' as a formula and '#N/A' as an error value, so a note like
    '=> use for jump' produced a workbook Excel calls corrupt and '=HYPERLINK(...)'
    would have run on open. Every string cell write_xlsx makes must be text."""
    cfg = Config(name="Formulas", filename="=weird.csv")
    cfg.modes.append(Mode(number=1, name="=Aim", label="=Aim", channel="usb", mappings=[
        Mapping(row=4, output="cross", function="normal", params=[], inputs=["lip"],
                comment="=> use for jump"),
        Mapping(row=5, output="circle", function="repeat", params=[100], inputs=["right_sip"],
                comment='=HYPERLINK("http://x","x")'),
        Mapping(row=6, output="mouse_speed", function="", params=[], inputs=[],
                kind="preference", value="#N/A", comment="=SUM(A1:A2)"),
    ]))
    out = tmp_path / "formulas.xlsx"
    write_xlsx(cfg, str(out))

    wb = load_workbook(out)                 # not read_only: data_type must be inspectable
    try:
        ws = wb["=Aim"]                     # sheet_title only rewrites []:*?/\\
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    assert c.data_type == "s", f"{c.coordinate} is {c.data_type}: {c.value!r}"
        assert ws["A2"].value == "=weird.csv"
        assert ws["C1"].value == "=Aim"
        assert ws["K4"].value == "=> use for jump"
        assert ws["K5"].value == '=HYPERLINK("http://x","x")'
        assert (ws["A6"].value, ws["C6"].value, ws["K6"].value) == ("mouse_speed", "#N/A", "=SUM(A1:A2)")
    finally:
        wb.close()

    again, problems = load(str(out))
    assert not [p for p in problems if p[0] == "error"], problems
    m = again.modes[0].mappings
    assert [x.comment for x in m] == ["=> use for jump", '=HYPERLINK("http://x","x")', "=SUM(A1:A2)"]
    assert (m[2].kind, m[2].value) == ("preference", "#N/A")


@pytest.mark.parametrize("name,expected", [
    ("Left joy", "Left joy"),
    ("a\\b", "a-b"),
    ("   ", "Mode 9"),
    ("trailing   ", "trailing"),
])
def test_sheet_title_cases(name, expected):
    assert sheet_title(name, set(), "Mode 9") == expected
