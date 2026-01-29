import enum
from PyQt6.QtCore import QObject, pyqtSignal

class SLMState(enum.Enum):
    DISABLED = "Disabled"
    CHECKING_RESOURCES = "Checking Resources"
    WAITING_FOR_USER = "Waiting for User"
    PROVISION_FAILED = "Provisioning Failed"
    NOT_AVAILABLE = "Not Available"
    DOWNLOADING_SOURCE = "Downloading Source Model"
    CONVERTING_MODEL = "Converting Model"
    LOADING = "Loading Model"
    READY = "Ready"
    INFERRING = "Refining..."
    ERROR = "Error"

class ProvisioningSignals(QObject):
    """Signals for the ProvisioningWorker."""
    progress = pyqtSignal(str)  # Status message
    finished = pyqtSignal(bool, str)  # Success, Error Message
