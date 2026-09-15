"""Data model: Config -> Mode -> Mapping. Mirrors the intended Postgres schema."""
from dataclasses import dataclass, field


@dataclass
class Mapping:
    row: int                      # spreadsheet row number (1-based) for error messages
    output: str
    function: str
    params: list                  # ints as parsed; a token that is not a whole number
                                  # ('five', '2.5') is kept as the raw str so write_csv
                                  # reproduces the file byte for byte, and validate()
                                  # reports it (catalog.function_errors)
    inputs: list                  # ordered, columns C..J; empty list = unused row.
                                  # 2+ inputs = a sequence performed in column order (C first).
    comment: str = ""
    kind: str = "mapping"         # "mapping" | "preference" (per-mode override: A = preference
                                  # name, B empty, C = value; unverified on a device, see docs)
    value: str = ""               # preference override value (kind == "preference")

    def is_sequence(self):
        return self.kind == "mapping" and len(self.inputs) > 1


@dataclass
class Mode:
    number: int                   # tab position, 1-based
    name: str                     # tab name
    label: str                    # C1 e.g. "Left joy"
    channel: str                  # C3 usb / bluetooth
    mappings: list = field(default_factory=list)

    def active(self):
        return [m for m in self.mappings if m.inputs]


@dataclass
class Config:
    name: str                     # workbook / spreadsheet name
    filename: str                 # A2 of first sheet, e.g. ddfortnite.csv
    modes: list = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    reference_card: list = field(default_factory=list)  # raw rows, if a sheet exists
    game: str = ""
    console: str = "playstation"   # naming set used in the source sheet
    source_url: str = ""           # Google Sheet URL from the CSV header, if any
    format_version: str = "Version 1.4"
