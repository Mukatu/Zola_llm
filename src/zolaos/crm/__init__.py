"""CRM — pipeline commercial du cabinet (amont : prospect → mission)."""

from zolaos.crm.pipeline import (
    OPEN_STAGES,
    STAGE_PROBABILITY,
    STAGES,
    default_probability,
    summarize_pipeline,
)

__all__ = [
    "OPEN_STAGES",
    "STAGES",
    "STAGE_PROBABILITY",
    "default_probability",
    "summarize_pipeline",
]
