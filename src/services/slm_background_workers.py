import time
import logging
from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    QRunnable,
)

from src.core.config_manager import ConfigManager
from src.core.model_registry import SupportedModel
from src.provisioning.core import provision_model
from src.services.slm_types import ProvisioningSignals

logger = logging.getLogger(__name__)

class _WorkerSignals(QObject):
    """Signals for background workers."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class ProvisioningWorker(QRunnable):
    """
    Background worker that delegates model provisioning to src.provisioning.core.
    Adaptor pattern to bridge core logic with Qt Signals.
    """

    def __init__(
        self, model: SupportedModel, cache_dir: Path, source_dir: Path | None = None
    ):
        super().__init__()
        self.model = model
        self.cache_dir = cache_dir
        self.source_dir = source_dir
        self.signals = ProvisioningSignals()
        self.logger = logger

    def run(self) -> None:
        try:
            # Define progress callback adaptor
            def progress_callback(msg: str):
                self.signals.progress.emit(msg)

            # Delegate to core library
            provision_model(
                self.model,
                self.cache_dir,
                progress_callback=progress_callback,
                source_dir=self.source_dir,
            )

            self.signals.finished.emit(True, "Provisioning complete.")

        except Exception as e:
            self.logger.error(f"Provisioning worker failed: {e}")
            self.signals.finished.emit(False, str(e))

class _MOTDWorker(QRunnable):
    """Background worker for MOTD generation."""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.signals = _WorkerSignals()

    def run(self):
        """Execute MOTD generation in background thread."""
        try:
            system_prompt = (
                "You are a creative assistant embedded in a desktop application."
            )
            if ConfigManager:
                system_prompt = (
                    ConfigManager.get_config_value("prompts", "motd_system")
                    or system_prompt
                )

            constraints = [
                "Write exactly one sentence (5–20 words).",
                "Tone must be calm, grounded, professional, and engaging.",
                "Avoid overly dramatic language; subtle poetic elements and wordplay are encouraged.",
                "Do not use emojis.",
                "Do not produce slogans or marketing copy.",
                "Respond with ONLY the message itself. No preamble, explanation, or additional text.",
            ]

            guidance = [
                "Be creatively engaging within the tone constraints.",
                "Incorporate subtle wordplay, alliteration, varied phrasing, or light humor to make the message unique and memorable.",
                "Draw inspiration from themes like nature, technology, creativity, or daily life to add depth.",
                "Ensure each message feels fresh and different from previous ones.",
            ]

            user_prompt = "\n".join(
                (
                    "Task:",
                    "Generate a message-of-the-day for a speech-to-text application named Vociferous.",
                    "",
                    "Hard constraints:",
                    *[f"- {rule}" for rule in constraints],
                    "",
                    "Soft guidance:",
                    *[f"- {note}" for note in guidance],
                    "",
                    f"Uniqueness seed: {int(time.time())}",
                )
            )

            motd_result = self.engine.generate_custom(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=75,  # Tighter token budget for concise output
                temperature=1.15,
            )

            logger.debug(f"MOTD raw result: {motd_result}")

            if motd_result and motd_result.content:
                motd = motd_result.content.strip().strip('"')
                logger.debug(f"MOTD after processing: {motd}")
                self.signals.finished.emit(motd)
            else:
                logger.warning(
                    f"Empty MOTD result: content={motd_result.content if motd_result else None}"
                )
                self.signals.error.emit("Empty MOTD result")

        except Exception as e:
            logger.exception("MOTD worker failed")
            self.signals.error.emit(str(e))
