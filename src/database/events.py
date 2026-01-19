from dataclasses import dataclass, field
from enum import Enum, auto


class ChangeAction(Enum):
    CREATED = auto()
    UPDATED = auto()
    DELETED = auto()
    BATCH_COMPLETED = auto()


@dataclass(slots=True, frozen=True)
class EntityChange:
    entity_type: str  # e.g., "transcription", "project"
    action: ChangeAction
    ids: list[int] = field(default_factory=list)
    reload_required: bool = False
