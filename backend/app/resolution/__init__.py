"""Entity resolution: cluster records that represent the same real-world entity.

Pipeline: blocking -> candidate pairs -> weighted scoring -> classification ->
transitive-closure clustering -> survivorship (golden record) -> persistence, with
MID-confidence pairs routed to the human review queue.
"""
from app.resolution.router import router
from app.resolution.service import ResolutionService

__all__ = ["router", "ResolutionService"]
