"""SLM types for Vociferous v4.0."""

import enum


class SLMState(enum.Enum):
    DISABLED = "Disabled"
    CHECKING_RESOURCES = "Checking Resources"
    WAITING_FOR_USER = "Waiting for User"
    PROVISION_FAILED = "Provisioning Failed"
    NOT_AVAILABLE = "Not Available"
    DOWNLOADING = "Downloading Model"
    LOADING = "Loading Model"
    READY = "Ready"
    INFERRING = "Refining..."
    ERROR = "Error"
