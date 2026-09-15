"""Which operating system this copy is running on.

One place, so the launcher and the desktop API cannot drift apart: `os.name`
answers for Windows, `sys.platform` for macOS, and everything else is treated as
Linux/BSD. Not named `platform.py` — that would shadow the standard library for
everything else on `sys.path`, and `desktop/` is on `sys.path` when frozen.
"""
import os
import sys

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
