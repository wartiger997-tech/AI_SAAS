"""Vercel entrypoint shim.

Vercel resolves ``main:app`` relative to the service root. The real application
lives in the installable ``redliner`` package under ``src/``. Adding ``src`` to
``sys.path`` keeps the function import working even if the package metadata is
not present in the runtime bundle.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from redliner.main import app

__all__ = ["app"]