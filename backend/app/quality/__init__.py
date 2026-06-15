"""Data quality scoring for Base Camp records.

Pure, DB-free scoring of a record against its schema. See ``scoring.score_record``.
"""

from app.quality.scoring import score_record

__all__ = ["score_record"]
