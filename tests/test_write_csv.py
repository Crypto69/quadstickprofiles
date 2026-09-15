"""write_csv / write_prefs_csv write ASCII only. validate() refuses non-ASCII (D4), so
anything that still reaches the writer is a bug in a caller; it must raise, not
silently turn the character into '?' and hand the device a different keyword."""
import pathlib
import pytest
from qsprofile import Config, Mode, Mapping, load, write_csv
from qsprofile.convert import write_prefs_csv

FX = pathlib.Path(__file__).parent.parent / "fixtures"


def _cfg(label="Left joy"):
    m = Mode(number=1, name="Mode", label=label, channel="usb")
    m.mappings.append(Mapping(row=4, output="increment_mode", function="normal", params=[], inputs=["right_sip"]))
    return Config(name="Test", filename="test.csv", modes=[m])


def test_non_ascii_label_raises_instead_of_writing_a_question_mark(tmp_path):
    out = tmp_path / "out.csv"
    with pytest.raises(UnicodeEncodeError):
        write_csv(_cfg(label="Café"), str(out))


def test_non_ascii_preference_value_raises_in_prefs_csv(tmp_path):
    out = tmp_path / "prefs.csv"
    with pytest.raises(UnicodeEncodeError):
        write_prefs_csv({"bluetooth_device_name": "Stück"}, str(out))


def test_failed_write_leaves_no_file_behind(tmp_path):
    """The encode raises before the target is opened, so the CLI never leaves a
    0-byte .csv on the export share."""
    out = tmp_path / "out.csv"
    with pytest.raises(UnicodeEncodeError):
        write_csv(_cfg(label="Café"), str(out))
    assert not out.exists()
    prefs = tmp_path / "prefs.csv"
    with pytest.raises(UnicodeEncodeError):
        write_prefs_csv({"bluetooth_device_name": "Stück"}, str(prefs))
    assert not prefs.exists()


def test_failed_write_keeps_the_existing_file(tmp_path):
    out = tmp_path / "out.csv"
    write_csv(_cfg(), str(out))
    before = out.read_bytes()
    with pytest.raises(UnicodeEncodeError):
        write_csv(_cfg(label="Café"), str(out))
    assert out.read_bytes() == before


def test_ascii_content_still_writes(tmp_path):
    out = tmp_path / "out.csv"
    write_csv(_cfg(), str(out))
    assert out.read_bytes().startswith(b"QuadStick Configuration,Version 1.4,,Test\r\nProfile Name,,Left joy,\r\n")


@pytest.mark.parametrize("name", ["ddfortnite.csv", "cod.csv", "synthetic_pref_override.csv"])
def test_strict_encoding_leaves_fixture_bytes_unchanged(name, tmp_path):
    cfg, _ = load(str(FX / name))
    out = tmp_path / name
    write_csv(cfg, str(out))
    assert out.read_bytes() == (FX / name).read_bytes()
