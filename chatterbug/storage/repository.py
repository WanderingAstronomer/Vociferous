from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from chatterbug.domain.model import TranscriptionResult


class StorageRepository(Protocol):
    def save_transcription(self, result: TranscriptionResult, target: Path | None = None) -> Path | None:
        ...

    def load_history(self, limit: int) -> Iterable[TranscriptionResult]:
        ...

    def clear_history(self) -> None:
        ...


class FileSystemStorage(StorageRepository):
    """Filesystem-backed storage stub; persistence wiring is pending."""

    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir

    def save_transcription(self, result: TranscriptionResult, target: Path | None = None) -> Path | None:
        raise NotImplementedError("File saving not yet implemented")

    def load_history(self, limit: int) -> Iterable[TranscriptionResult]:
        return iter(())

    def clear_history(self) -> None:
        pass
