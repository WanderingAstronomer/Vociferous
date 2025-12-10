"""Composable CLI command registrations for Typer."""

from .decode import register_decode
from .vad import register_vad
from .condense import register_condense
from .record import register_record
from .refine import register_refine

__all__ = [
    "register_decode",
    "register_vad",
    "register_condense",
    "register_record",
    "register_refine",
]
