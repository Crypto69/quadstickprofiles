"""Seed the catalogs from core/qsprofile/catalog.py and import the fixtures.

    python -m app.seed                # catalogs + fixtures (idempotent)
    python -m app.seed --catalog-only
"""
import json
import sys
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from qsprofile import load
from . import models as M
from .bridge import profile_from_config
from .catalog_seed import input_rows, output_rows, function_rows
from .db import SessionLocal
from .settings import settings

# fixture file -> (actions file, display name override, starter-profile note or None)
#
# A starter profile is one you copy from rather than play with, so it is kept
# on its own shelf in the library and offered when creating a profile. The device
# CSVs stay as ordinary profiles: they are his live files, and a re-export of one
# must still be byte-identical to what is on the flash drive.
FIXTURES = {
    "ddfortnite.csv": ("actions_fortnite.json", "ddfortnite", None),
    "cod.csv": ("actions_cod.json", "Call of Duty", None),
    "ddfortnite.xlsx": ("actions_fortnite.json", "Fortnite starter",
                        "Seven modes built around the left stick, the right stick and the D-pad, "
                        "with Fortnite's button names already filled in. A good base for any "
                        "third-person shooter."),
    "Call_of_Duty.xlsx": ("actions_cod.json", "Call of Duty starter",
                          "Eight modes including a gyro mode, with Call of Duty's button names. "
                          "A good base for a first-person shooter."),
    "Call_of_Duty_Advanced_Warfare_XBox_One.xlsx": (
        "actions_cod.json", "Xbox-named starter",
        "The same idea under Xbox button names, for a PC or an Xbox. Five modes."),
    # synthetic, unverified on a device: the only per-mode
    # preference override example, so the DB round-trip for kind="preference" is seeded
    "synthetic_pref_override.csv": ("actions_cod.json", "Per-mode override (synthetic, unverified)",
                                    None),
}


def _upsert(db: Session, model, rows):
    """One SELECT per table instead of a `db.get` per row (538 round-trips on every
    container start and every desktop launch). Existing rows still have their fields
    refreshed from the catalog, so a renamed label reaches an already-seeded database;
    only fields that actually differ are written, so unchanged rows stay clean.
    Rows this seed does not know about (ensure_output's kb_* / ir_*) are left alone."""
    existing = {o.name: o for o in db.scalars(select(model))}
    new = []
    for r in rows:
        obj = existing.get(r["name"])
        if obj is None:
            new.append(model(**r))
        else:
            for k, v in r.items():
                if getattr(obj, k) != v:
                    setattr(obj, k, v)
    db.add_all(new)


def seed_catalogs(db: Session):
    _upsert(db, M.InputCatalog, input_rows())
    _upsert(db, M.OutputCatalog, output_rows())
    _upsert(db, M.FunctionCatalog, function_rows())
    db.commit()


def game_action_rows(actions: dict, profile_id=None):
    rows = []
    for out, act in actions.get("outputs", {}).items():
        if act:
            rows.append(M.GameAction(profile_id=profile_id, game=actions["game"], output=out, action=act))
    for mode_name, outs in actions.get("modes", {}).items():
        for out, act in outs.items():
            if act:
                rows.append(M.GameAction(profile_id=profile_id, game=actions["game"], mode_name=mode_name,
                                         output=out, action=act))
    return rows


def seed_templates(db: Session, actions_dir: Path):
    """Shared (profile_id NULL) game-action templates, one per actions_*.json."""
    for f in sorted(actions_dir.glob("actions_*.json")):
        actions = json.loads(f.read_text())
        exists = db.scalar(select(M.GameAction.id).where(M.GameAction.profile_id.is_(None),
                                                         M.GameAction.game == actions["game"]).limit(1))
        if exists:
            continue
        db.add_all(game_action_rows(actions))
    db.commit()


def seed_fixtures(db: Session, fixtures_dir: Path, actions_dir: Path):
    imported = []
    for fname, (actions_file, display, template_note) in FIXTURES.items():
        path = fixtures_dir / fname
        if not path.exists():
            print(f"  skip {fname}: not found")
            continue
        if db.scalar(select(M.Profile.id).where(M.Profile.name == display).limit(1)):
            print(f"  skip {fname}: '{display}' already imported")
            continue
        actions = json.loads((actions_dir / actions_file).read_text())
        cfg, _problems = load(str(path))
        p = profile_from_config(db, cfg, game=actions["game"])
        p.name = display
        # The owner's PlayStation profiles run DualShock 4 emulation (mode 4) through the
        # Brook Wingman, but none of his files carries an enable_DS3_emulation row: the
        # device takes it from prefs.csv. The seed adds nothing, so a re-export of a
        # device CSV stays byte-identical (decision D1).
        if template_note:
            p.is_template = True
            p.template_note = template_note
        p.notes = f"Imported from fixtures/{fname}"
        p.game_actions = game_action_rows(actions)
        p.input_names = [M.InputName(input=k, name=v) for k, v in actions.get("inputs", {}).items()]
        db.add(p)
        db.commit()
        imported.append((p.id, display, len(p.modes)))
        print(f"  imported {fname} -> profile {p.id} '{display}' ({len(p.modes)} modes, {cfg.console}, "
              f"firmware {p.firmware}"
              f"{', starter profile' if p.is_template else ''})")
    return imported


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with SessionLocal() as db:
        print("seeding catalogs from qsprofile.catalog")
        seed_catalogs(db)
        if "--catalog-only" in argv:
            return 0
        print("seeding shared game-action templates")
        seed_templates(db, settings.actions_dir)
        print("importing fixtures")
        seed_fixtures(db, settings.fixtures_dir, settings.actions_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
