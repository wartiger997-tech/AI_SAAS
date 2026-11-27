"""Vercel entrypoint shim.

Vercel resolves ``main:app`` relative to the service root. The real application
lives in the installable ``voice_api`` package under ``src/``.
"""

from voice_api.main import app

__all__ = ["app"]