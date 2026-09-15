"""The catalog seed runs on every container start, every desktop launch and before
every test, so it has to be both idempotent and cheap (N5), and it has to carry every
name core accepts (C1)."""
from sqlalchemy import func, select
from qsprofile import catalog as C
from app import models as M
from app.catalog_seed import input_rows, output_rows, function_rows
from app.seed import seed_catalogs


def _counts(db):
    return tuple(db.scalar(select(func.count()).select_from(m))
                 for m in (M.InputCatalog, M.OutputCatalog, M.FunctionCatalog))


def test_seeding_twice_changes_nothing(db):
    """conftest already seeded once; a second pass must not duplicate or drop a row."""
    before = _counts(db)
    assert before == (len(input_rows()), len(output_rows()), len(function_rows()))
    seed_catalogs(db)
    assert _counts(db) == before
    names = db.scalars(select(M.InputCatalog.name)).all()
    assert len(names) == len(set(names))


def test_the_seed_refreshes_a_stale_label(db):
    """The one thing the old per-row db.get loop did that a plain insert-missing
    would lose: an existing row's fields are brought back in line with the catalog."""
    row = db.get(M.OutputCatalog, "x")
    original = row.label
    row.label = "stale"
    db.commit()
    seed_catalogs(db)
    assert db.get(M.OutputCatalog, "x").label == original == C.OUTPUTS["x"]


def test_the_seed_leaves_rows_it_does_not_own_alone(db):
    """ensure_output adds kb_* / ir_* rows at sort_order 10_000 on first sight;
    the seed must not delete or renumber them."""
    db.add(M.OutputCatalog(name="kb_seed_probe", grp="keyboard", label="probe", sort_order=10_000))
    db.commit()
    seed_catalogs(db)
    probe = db.get(M.OutputCatalog, "kb_seed_probe")
    assert probe is not None and probe.sort_order == 10_000 and probe.label == "probe"
    db.delete(probe)
    db.commit()


def test_the_seed_does_one_select_per_table(db):
    """N5: the loop used to issue a db.get per row (538 round-trips every start)."""
    from sqlalchemy import event
    seen = []
    engine = db.get_bind()

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            seen.append(statement)

    try:
        seed_catalogs(db)
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    assert len(seen) <= 3, f"{len(seen)} SELECTs; expected one per catalog table:\n" + "\n".join(seen)
