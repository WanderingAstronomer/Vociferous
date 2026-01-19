from dataclasses import dataclass
from enum import Enum, auto


class EngineState(Enum):
    """Execution states for the engine."""

    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    COMPLETE = auto()
    ERROR = auto()


@dataclass(slots=True)
class TranscriptionResult:
    """Unified result data from transcription."""

    state: EngineState
    text: str = ""
    duration_ms: int = 0
    speech_duration_ms: int = 0
    error_message: str = ""
