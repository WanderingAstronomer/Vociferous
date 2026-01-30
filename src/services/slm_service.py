raise ImportError("SLMService has been removed. Import SLMRuntime from src.services.slm_runtime instead.")

# Legacy module intentionally removed and disabled to avoid accidental usage
# This file is kept only as a sentinel. Do not reintroduce SLMService; prefer
# the focused SLMRuntime and small focused provisioning components.

import logging
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtCore import (
    QObject,
    QTimer,
    pyqtSignal,
    pyqtSlot,
    QThreadPool,
)

from src.core.config_manager import ConfigManager, get_model_cache_dir
from src.core.model_registry import MODELS, SupportedModel
from src.services.slm_types import SLMState
from src.services.slm_background_workers import ProvisioningWorker, _MOTDWorker
from src.services.slm_utils import get_gpu_memory_map, validate_model_artifacts

# Conditional imports to defer dependencies until needed
try:
    from src.refinement.engine import RefinementEngine
except ImportError:
    RefinementEngine = None  # type: ignore

logger = logging.getLogger(__name__)


class SLMService(QObject):
    """
    Background service for managing the Small Language Model (SLM) Lifecycle.
    Handles downloading, loading, and running the refinement engine.
    """

    # Signals
    stateChanged = pyqtSignal(object)  # param: SLMState
    progress = pyqtSignal(
        str, str, int, int, bool
    )  # job_id, stage, current, total, indeterminate
    statusMessage = pyqtSignal(str)
    motdReady = pyqtSignal(str)  # Emitted when MOTD is generated

    # Global UI Blocking Signal
    # bool: True = Block/Busy, False = Unblock
    serviceBusy = pyqtSignal(bool, str)

    refinementSuccess = pyqtSignal(int, str)  # transcript_id, text
    refinementError = pyqtSignal(int, str)  # transcript_id, error_message

    # Request Main Thread UI interaction
    askGPUConfirmation = pyqtSignal(int, int, int)  # free_mb, total_mb, needed_mb

    # Engine heartbeat control (for long-running operations)
    requestHeartbeatPause = pyqtSignal()
    requestHeartbeatResume = pyqtSignal()

    # Artifact Layout
    SOURCE_DIR_NAME = "slm-source-temp"
    EXPECTED_ARTIFACTS = ["model.bin", "config.json", "vocabulary.json"]

    def __init__(self):
        super().__init__()
        self._state = SLMState.DISABLED
        self._engine: Optional[RefinementEngine] = None
        self._abort_download = False

        # Background worker support
        self._threadpool = QThreadPool()
        self._pending_model_id: Optional[str] = None
        self._is_provisioning = False

        # Request Queue
        self._request_queue: list[
            tuple
        ] = []  # Stores pending requests as (args, kwargs)

        # Configurable maximum request queue size (default 5)
        try:
            self._max_queue_size = ConfigManager.get_value("refinement", "max_queue_size", default=5)
        except Exception:
            # ConfigManager may not be initialized in some test contexts; fall back safely
            self._max_queue_size = 5

        # Determine initial model from config
        model_id = "qwen4b"
        if ConfigManager:
            model_id = (
                ConfigManager.get_config_value("refinement", "model_id") or "qwen4b"
            )

        self.current_model = MODELS.get(model_id, MODELS["qwen4b"])

        # Synchronization for User Input (non-blocking GPU confirmation)
        # Historically we used a blocking wait for GPU confirmation which led to
        # UI deadlocks. We now use an async emit + queued submit pattern and no
        # longer need the blocking primitives. Keep only the choice storage.
        self._user_gpu_choice = False
        # Store pending initialization state when waiting for GPU confirmation
        self._pending_init_model_dir: Optional[Path] = None
        self._pending_init_tokenizer_json: Optional[Path] = None
        # Timeout for GPU confirmation (seconds)
        self._gpu_confirmation_timeout_ms = 30000  # 30 seconds
        self._gpu_timeout_timer: Optional[Any] = None

    @classmethod
    def get_supported_models(cls) -> list[SupportedModel]:
        return list(MODELS.values())

    @pyqtSlot(str)
    def change_model(self, model_id: str):
        """Switch active model at runtime."""
        if model_id not in MODELS:
            logger.error(f"Unknown model ID: {model_id}")
            return

        new_model = MODELS[model_id]
        if new_model.id == self.current_model.id and self._state == SLMState.READY:
            logger.info("New model is same as current active model. No action.")
            return

        self._pending_model_id = model_id

        # Check if new model is ready to go
        cache_dir = get_model_cache_dir()
        model_dir = cache_dir / new_model.dir_name

        if validate_model_artifacts(model_dir):
            # Ready? Switch immediately.
            logger.info(f"Model {new_model.name} is ready. Switching immediately.")
            self._finalize_model_switch(new_model)
        else:
            # Not ready? Start background provisioning
            logger.info(
                f"Model {new_model.name} requires provisioning. Starting background task..."
            )
            self.statusMessage.emit(f"Downloading {new_model.name} in background...")
            self._start_background_provisioning(new_model)

    def _start_background_provisioning(self, model: SupportedModel):
        """Start the provisioning worker."""
        if self._is_provisioning:
            logger.warning("Provisioning already in progress.")
            self.statusMessage.emit("Wait for current download to finish.")
            return

        # We no longer block here if dependencies are missing;
        # the ProvisioningWorker will attempt to install them automatically.
        self.statusMessage.emit("Starting model provisioning...")

        self._is_provisioning = True
        cache_dir = get_model_cache_dir()

        worker = ProvisioningWorker(model, cache_dir)
        worker.signals.progress.connect(self._on_provisioning_progress)
        worker.signals.finished.connect(self._on_provisioning_finished)

        self._threadpool.start(worker)

    @pyqtSlot(str)
    def _on_provisioning_progress(self, msg: str):
        """Handle progress updates from worker."""
        logger.info(f"Provisioning: {msg}")
        # Show progress to user via status message
        self.statusMessage.emit(f"⏳ {msg}")

    @pyqtSlot(bool, str)
    def _on_provisioning_finished(self, success: bool, msg: str):
        """Handle worker completion."""
        self._is_provisioning = False

        # Resume engine heartbeat now that heavy work is done
        self.requestHeartbeatResume.emit()

        if success:
            logger.info("Background provisioning complete checking pending model...")

            if self._pending_model_id:
                target_model = MODELS.get(self._pending_model_id)
                # Only switch if we are strictly changing models
                if target_model and target_model.id != self.current_model.id:
                    self.statusMessage.emit(f"Switching to {target_model.name}...")
                    self._finalize_model_switch(target_model)
                else:
                    self.statusMessage.emit("Model ready.")
        else:
            logger.error(f"Provisioning failed: {msg}")
            self.statusMessage.emit(f"Provisioning failed: {msg}")
            self._pending_model_id = None
            # Ensure we reset state so UI unblocks
            self._set_state(SLMState.PROVISION_FAILED)

    def _finalize_model_switch(self, new_model: SupportedModel):
        """Perform the actual switch and reload."""
        self.current_model = new_model

        # Unload current engine
        self._engine = None

        # Reset State
        self._set_state(SLMState.DISABLED)

        # Re-initialize (which will now find artifacts and load engine)
        self.initialize_service()

    def disable_service(self) -> None:
        """Disable the refinement service and unload the model from memory."""
        logger.info("Disabling SLM service and unloading model...")
        # Unload current engine
        self._engine = None
        # Set state to disabled
        self._set_state(SLMState.DISABLED)
        self.statusMessage.emit("Refinement disabled")

    @property
    def state(self) -> SLMState:
        return self._state

    def _set_state(self, new_state: SLMState):
        if self._state != new_state:
            self._state = new_state
            self.stateChanged.emit(new_state)
            self.statusMessage.emit(f"Refinement: {new_state.value}")

            # Emit busy signal for blocking operations
            is_blocking = new_state in (
                SLMState.CHECKING_RESOURCES,
                SLMState.WAITING_FOR_USER,
                SLMState.DOWNLOADING_SOURCE,
                SLMState.CONVERTING_MODEL,
                SLMState.LOADING,
            )
            self.serviceBusy.emit(is_blocking, new_state.value)

            # Drain queue if we just became READY
            if new_state == SLMState.READY:
                self._drain_request_queue()

    def _drain_request_queue(self):
        """Process any pending requests that were blocked during initialization."""
        if not self._request_queue:
            return

        logger.info(
            f"Draining {len(self._request_queue)} pending refinement requests..."
        )

        while self._request_queue:
            if self.state != SLMState.READY:
                break

            item = self._request_queue.pop(0)
            logger.debug(f"Processing queued request: {item}")

            if len(item) == 5:
                tid, txt, prof, inst, kw = item
                self.handle_refinement_request(tid, txt, prof, inst, **kw)
            else:
                self.handle_refinement_request(*item)

    def _start_gpu_confirmation_timeout(self):
        """Start a timeout timer for GPU confirmation dialog."""
        self._cancel_gpu_confirmation_timeout()

        self._gpu_timeout_timer = QTimer()
        self._gpu_timeout_timer.setSingleShot(True)
        self._gpu_timeout_timer.timeout.connect(self._on_gpu_confirmation_timeout)
        self._gpu_timeout_timer.start(self._gpu_confirmation_timeout_ms)
        logger.info(
            f"GPU confirmation timeout started ({self._gpu_confirmation_timeout_ms}ms). "
            "Will default to CPU if no response."
        )

    def _cancel_gpu_confirmation_timeout(self):
        """Cancel the GPU confirmation timeout timer."""
        if self._gpu_timeout_timer is not None:
            self._gpu_timeout_timer.stop()
            self._gpu_timeout_timer.deleteLater()
            self._gpu_timeout_timer = None

    @pyqtSlot()
    def _on_gpu_confirmation_timeout(self):
        """Handle GPU confirmation timeout - default to CPU."""
        logger.warning(
            "GPU confirmation timed out after "
            f"{self._gpu_confirmation_timeout_ms / 1000:.0f}s. Defaulting to CPU."
        )
        self._gpu_timeout_timer = None

        if self.state != SLMState.WAITING_FOR_USER:
            return

        if (
            self._pending_init_model_dir is not None
            and self._pending_init_tokenizer_json is not None
        ):
            model_dir = self._pending_init_model_dir
            tokenizer_json = self._pending_init_tokenizer_json
            self._pending_init_model_dir = None
            self._pending_init_tokenizer_json = None

            self.statusMessage.emit("No response - using CPU for safety.")
            self._load_engine(model_dir, tokenizer_json, "cpu")

    @pyqtSlot(bool)
    def submit_gpu_choice(self, use_gpu: bool):
        """Receive user choice from main thread and continue initialization."""
        self._cancel_gpu_confirmation_timeout()

        # Store user choice; processing continues on the service thread via queued invocation.
        self._user_gpu_choice = use_gpu

        if (
            self._pending_init_model_dir is not None
            and self._pending_init_tokenizer_json is not None
        ):
            model_dir = self._pending_init_model_dir
            tokenizer_json = self._pending_init_tokenizer_json
            self._pending_init_model_dir = None
            self._pending_init_tokenizer_json = None

            device = "cuda" if use_gpu else "cpu"
            self._load_engine(model_dir, tokenizer_json, device)

    @pyqtSlot()
    def initialize_service(self):
        """Called when feature is enabled or first used."""
        if self.state in (SLMState.READY, SLMState.INFERRING):
            return

        self._set_state(SLMState.CHECKING_RESOURCES)

        if RefinementEngine is None:
            logger.warning("Refinement dependencies not installed")
            self.statusMessage.emit("Refinement unavailable: dependencies not installed")
            self._set_state(SLMState.NOT_AVAILABLE)
            return

        try:
            cache_dir = get_model_cache_dir()
            model_dir = cache_dir / self.current_model.dir_name
            tokenizer_json = model_dir / "tokenizer.json"

            if not validate_model_artifacts(model_dir):
                logger.info("Model artifacts missing. Starting provisioning...")
                self.statusMessage.emit(
                    "⏳ First-run setup: Downloading and converting model. This may take several minutes..."
                )
                self.requestHeartbeatPause.emit()
                self._start_background_provisioning(self.current_model)
                self._set_state(SLMState.DOWNLOADING_SOURCE)
                return

            device = "cpu"
            mem_info = get_gpu_memory_map()
            if mem_info:
                total_mb, free_mb = mem_info
                MODEL_SIZE_MB = self.current_model.required_vram_mb
                headroom_ratio = (free_mb - MODEL_SIZE_MB) / total_mb

                if headroom_ratio >= 0.40:
                    device = "cuda"
                elif headroom_ratio < 0.20:
                    self._set_state(SLMState.WAITING_FOR_USER)
                    self._pending_init_model_dir = model_dir
                    self._pending_init_tokenizer_json = tokenizer_json
                    self._start_gpu_confirmation_timeout()
                    self.askGPUConfirmation.emit(free_mb, total_mb, MODEL_SIZE_MB)
                    return
                else:
                    device = "cuda"
            else:
                device = "cpu"

            self._load_engine(model_dir, tokenizer_json, device)

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.statusMessage.emit(f"Setup Error: {str(e)[:50]}")
            self._set_state(SLMState.ERROR)

    @pyqtSlot(int, str, str)
    @pyqtSlot(int, str, str, str)
    def handle_refinement_request(
        self,
        transcript_id: int,
        text: str,
        profile: str = "BALANCED",
        user_instructions: str = "",
        **kwargs,
    ):
        """Process a refinement request."""
        if self.state == SLMState.DISABLED:
            self.statusMessage.emit("Initializing Refinement Service...")
            self.initialize_service()

        if self.state == SLMState.ERROR:
            self.refinementError.emit(transcript_id, "Refinement service is in error state.")
            return

        if self.state != SLMState.READY:
            logger.info(f"Service busy/loading ({self.state.value}). Enqueuing request {transcript_id}.")

            # Deduplicate: if a request for the same transcript_id exists, replace it
            for i, item in enumerate(self._request_queue):
                try:
                    existing_tid = item[0]
                except Exception:
                    existing_tid = None
                if existing_tid == transcript_id:
                    self._request_queue[i] = (transcript_id, text, profile, user_instructions, kwargs)
                    self.statusMessage.emit("Request updated in queue.")
                    return

            # Capacity check: reject new requests when queue is full
            if len(self._request_queue) >= self._max_queue_size:
                self.statusMessage.emit(
                    f"Refinement queue full ({self._max_queue_size}). Please try again later."
                )
                self.refinementError.emit(transcript_id, "Refinement queue full")
                return

            # Normal enqueue
            self._request_queue.append((transcript_id, text, profile, user_instructions, kwargs))
            self.statusMessage.emit("Request queued. Waiting for service...")
            return

        if not self._engine:
            self.refinementError.emit(transcript_id, "Engine not loaded.")
            return

        try:
            self._set_state(SLMState.INFERRING)
            self.statusMessage.emit(f"Refining transcript ({profile})...")
            result = self._engine.refine(text, profile, user_instructions, **kwargs)
            if result.reasoning:
                logger.debug(f"Refinement Reasoning [ID={transcript_id}]: {result.reasoning}")
            self.refinementSuccess.emit(transcript_id, result.content)
            self._set_state(SLMState.READY)
            self.statusMessage.emit("Refinement complete.")
        except Exception as e:
            logger.error(f"Refinement error: {e}")
            self.refinementError.emit(transcript_id, f"Refinement failed: {str(e)}")
            self._set_state(SLMState.READY)

    @pyqtSlot()
    def generate_motd(self):
        """Generate a Message of the Day."""
        if self.state != SLMState.READY or not self._engine:
            return

        logger.info("Generating new Message of the Day...")
        self._set_state(SLMState.INFERRING)
        worker = _MOTDWorker(self._engine)
        worker.signals.finished.connect(self._on_motd_generated)
        worker.signals.error.connect(self._on_motd_error)
        QThreadPool.globalInstance().start(worker)

    def _on_motd_generated(self, motd: str):
        self.motdReady.emit(motd)
        self._set_state(SLMState.READY)

    def _on_motd_error(self, error_msg: str):
        logger.error(f"MOTD generation failed: {error_msg}")
        self._set_state(SLMState.READY)

    def _load_engine(self, model_path: Path, tokenizer_path: Path, device: str = "cpu"):
        """Load the Refinement Engine."""
        self._set_state(SLMState.LOADING)
        self.statusMessage.emit(f"Loading engine on {device.upper()}...")
        try:
            sys_prompt = ""
            invariants: list[str] = []
            levels: dict[int | str, dict[str, Any]] = {}
            if ConfigManager:
                sys_prompt = ConfigManager.get_config_value("prompts", "refinement_system") or ""
                invariants = ConfigManager.get_config_value("prompts", "refinement_invariants") or []
                levels = ConfigManager.get_config_value("prompts", "refinement_levels") or {}

            self._engine = RefinementEngine(
                model_path,
                tokenizer_path,
                system_prompt=sys_prompt,
                invariants=invariants,
                levels=levels,
                device=device,
                prompt_format=self.current_model.prompt_format,
            )
            self._set_state(SLMState.READY)
            self.statusMessage.emit("Refinement engine ready.")
        except Exception as e:
            logger.error(f"Engine load failed: {e}")
            self._set_state(SLMState.ERROR)
            self.statusMessage.emit(f"Load Error: {str(e)[:40]}")
