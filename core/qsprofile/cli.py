"""Command line front door.
  qsprofile card    <profile.xlsx|.csv> <actions.json> out.html
  qsprofile convert <profile.xlsx|.csv> playstation|xbox out.csv|out.xlsx [newname.csv]
  qsprofile check   <profile.xlsx|.csv>

Exit codes: 0 fine, 1 the profile has errors (or could not be read), 2 bad usage.
"""
import argparse
import json
import sys
import zipfile
from .parser import load
from .validate import validate
from .convert import convert, write_csv, write_xlsx
from .render import render


def _build_parser():
    p = argparse.ArgumentParser(prog="qsprofile", description=__doc__.strip().splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True, metavar="check|card|convert")

    c = sub.add_parser("check", help="list the findings for a profile")
    c.add_argument("profile", help="profile .xlsx or .csv")

    c = sub.add_parser("card", help="write the printable A4 reference card")
    c.add_argument("profile", help="profile .xlsx or .csv")
    c.add_argument("actions", help="actions .json (game-specific labels)")
    c.add_argument("out", help="output .html")

    c = sub.add_parser("convert", help="rename outputs for the other console and export")
    c.add_argument("profile", help="profile .xlsx or .csv")
    c.add_argument("target", choices=["playstation", "xbox"])
    c.add_argument("out", help="output .csv or .xlsx")
    c.add_argument("newname", nargs="?", default=None,
                   help="filename to write into the file's own A2 / line 2 cell")
    return p


def _load(path):
    """Read a profile, or (None, None) after a message on stderr — a file that is
    missing, unreadable or not a workbook is the owner's typo, not a bug to trace."""
    try:
        return load(path)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        print(f"could not read {path}: {e}", file=sys.stderr)
        return None, None


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.cmd == "convert" and not args.out.lower().endswith((".csv", ".xlsx")):
        parser.error(f"convert output must end in .csv or .xlsx, not '{args.out}'")

    cfg, problems = _load(args.profile)
    if cfg is None:
        return 1
    findings = validate(cfg, problems)
    has_errors = any(f[0] == "error" for f in findings)

    if args.cmd == "check":
        for sev, mode, row, msg in findings:
            where = " ".join(x for x in [f"mode {mode}" if mode else "", f"row {row}" if row else ""] if x)
            print(f"{sev:8} {where:14} {msg}")
        return 1 if has_errors else 0

    if args.cmd == "card":
        # the card is written whatever the findings: the Checks section on it is
        # exactly where the owner is meant to read them.
        try:
            with open(args.actions, encoding="utf-8") as f:
                actions = json.load(f)
        except (OSError, ValueError) as e:
            print(f"could not read {args.actions}: {e}", file=sys.stderr)
            return 1
        with open(args.out, "w", encoding="utf-8") as f:     # the card uses → and –
            f.write(render(cfg, actions, findings))
        print(f"wrote {args.out}")
        return 0

    # convert
    if has_errors:
        print("refusing to convert: fix errors first (run `qsprofile check`)", file=sys.stderr)
        return 1
    new, notes = convert(cfg, args.target)
    writer = write_csv if args.out.lower().endswith(".csv") else write_xlsx
    writer(new, args.out, args.newname)
    for n in notes:
        print(n)
    print(f"{cfg.console} -> {args.target}: wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
