"""Vercel entrypoint shim.

Vercel resolves ``main:app`` relative to the service root. The real application
lives in the installable ``redliner`` package under ``src/``.
"""

from redliner.main import app

__all__ = ["app"]