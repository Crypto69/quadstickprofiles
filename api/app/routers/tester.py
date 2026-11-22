"""The QuadStick tester: the `qstest` profile and the spec the tester page reads.

Both come from `core/qsprofile/tester.py`, one table, so the button-bit -> tube
map the page decodes is always the map the file on the device drives. Neither is
stored: like the reference card they are generated on request. Reading the
device itself happens in the browser (WebHID); nothing here touches USB.
"""
from fastapi import APIRouter, Response
from qsprofile import tester, write_csv
from ..headers import export_path_header
from .profiles import _export_target, write_atomically

router = APIRouter(prefix="/tester", tags=["tester"])


@router.get("/spec")
def spec():
    """Per mode: the d-pad direction it holds and which report bit is which input."""
    return tester.spec()


@router.get("/qstest.csv")
def qstest_csv():
    """The `qstest` profile to copy onto the flash drive. Also written to exports/."""
    out = _export_target(tester.FILENAME)
    data = write_atomically(out, lambda path: write_csv(tester.config(), path))
    return Response(data, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{tester.FILENAME}"',
                             "X-Export-Path": export_path_header(out)})
