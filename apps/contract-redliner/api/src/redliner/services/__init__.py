"""Service layer."""

from redliner.services.documents import create_document
from redliner.services.extraction import extract_clauses
from redliner.services.playbook import evaluate_clause, seed_default_playbooks
from redliner.services.redline import RenderFinding, RenderInput, render
from redliner.services.review import run_review

__all__ = [
    "RenderFinding",
    "RenderInput",
    "create_document",
    "evaluate_clause",
    "extract_clauses",
    "render",
    "run_review",
    "seed_default_playbooks",
]
