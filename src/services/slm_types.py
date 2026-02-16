"""SLM types for Vociferous v4.0."""

import enum


class SLMState(enum.Enum):
    DISABLED = "Disabled"
    LOADING = "Loading Model"
    READY = "Ready"
    INFERRING = "Refining..."
    ERROR = "Error"
