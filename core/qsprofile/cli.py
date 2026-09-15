"""Command line front door.
  qsprofile card    <profile.xlsx|.csv> <actions.json> out.html
  qsprofile convert <profile.xlsx|.csv> playstation|xbox out.csv|out.xlsx [newname.csv]
  qsprofile check   <profile.xlsx|.csv>
"""
import json
import sys
from .parser import load
from .validate import validate
from .convert import convert, write_csv, write_xlsx
from .render import render


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv or argv[0] not in ("card", "convert", "check"):
        print(__doc__); return 2
    cmd, args = argv[0], argv[1:]
    cfg, problems = load(args[0])
    findings = validate(cfg, problems)
    if cmd == "check":
        for sev, mode, row, msg in findings:
            where = " ".join(x for x in [f"mode {mode}" if mode else "", f"row {row}" if row else ""] if x)
            print(f"{sev:8} {where:14} {msg}")
        return 1 if any(f[0] == "error" for f in findings) else 0
    if cmd == "card":
        actions = json.load(open(args[1])) if len(args) > 1 else {}
        open(args[2], "w").write(render(cfg, actions, findings))
        print(f"wrote {args[2]}"); return 0
    if cmd == "convert":
        if any(f[0] == "error" for f in findings):
            print("refusing to convert: fix errors first (run `qsprofile check`)"); return 1
        new, notes = convert(cfg, args[1])
        newname = args[3] if len(args) > 3 else None
        (write_csv if args[2].lower().endswith(".csv") else write_xlsx)(new, args[2], newname)
        for n in notes: print(n)
        print(f"{cfg.console} -> {args[1]}: wrote {args[2]}"); return 0


if __name__ == "__main__":
    sys.exit(main())
