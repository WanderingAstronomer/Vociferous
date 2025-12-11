"""System interaction layer - AudioSource implementations.

This module provides application-level facades that compose audio primitives
into AudioSource implementations for different input sources.
"""

from .file import FileSource

__all__ = [
    "FileSource",
]
