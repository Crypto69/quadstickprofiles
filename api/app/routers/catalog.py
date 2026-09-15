from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from qsprofile import catalog as C
from .. import models as M, schemas as S
from ..db import get_session

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=S.CatalogOut)
def get_catalog(db: Session = Depends(get_session)):
    inputs = db.scalars(select(M.InputCatalog).order_by(M.InputCatalog.sort_order)).all()
    outputs = db.scalars(select(M.OutputCatalog).order_by(M.OutputCatalog.sort_order, M.OutputCatalog.name)).all()
    functions = db.scalars(select(M.FunctionCatalog).order_by(M.FunctionCatalog.sort_order)).all()
    return S.CatalogOut(
        inputs=[S.InputEntry.model_validate(i, from_attributes=True) for i in inputs],
        outputs=[S.OutputEntry.model_validate(o, from_attributes=True) for o in outputs],
        functions=[S.FunctionEntry.model_validate(f, from_attributes=True) for f in functions],
        tubes=C.TUBES, tube_order=C.TUBE_ORDER,
        joystick_directions=C.JOY_DIRS, joystick_zones=C.JOY_ZONES,
        digital_jacks=C.DIGITAL_JACKS, xbox_to_ps=C.XBOX_TO_PS,
        no_xbox_equivalent=sorted(C.NO_XBOX_EQUIVALENT),
        mode_change_outputs=sorted(C.MODE_CHANGE_OUTPUTS),
        output_families={"keyboard": C._KB_RE.pattern, "ir": C._IR_RE.pattern},
        preferences=C.PREFERENCES, preference_categories=list(C.PREFERENCE_CATEGORIES),
        mode_overridable=sorted(C.MODE_OVERRIDABLE),
        emulation_modes=C.EMULATION_MODES,
        hidden_drive_modes={fw: sorted(ms) for fw, ms in C.HIDDEN_DRIVE_MODES.items()},
        firmware_versions=list(C.FIRMWARE_VERSIONS), default_firmware=C.DEFAULT_FIRMWARE,
        legacy_inputs=C.LEGACY_INPUTS,
        limits={"max_modes": C.MAX_MODES, "max_rows_per_mode": C.MAX_ROWS_PER_MODE,
                "max_keyword_chars": C.MAX_KEYWORD_CHARS, "max_line_bytes": C.MAX_LINE_BYTES,
                "max_function_param": C.MAX_FUNCTION_PARAM},
    )
