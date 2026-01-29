import enum
import time
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtCore import (
    QMutex,
    QObject,
    QTimer,
    QWaitCondition,
    pyqtSignal,
    pyqtSlot,
    QThreadPool,
    QRunnable,
)

from src.core.config_manager import ConfigManager, get_model_cache_dir
from src.core.model_registry import MODELS, SupportedModel
from src.provisioning.core import provision_model, ProvisioningError

# Conditional imports to defer dependencies until needed
try:
    from huggingface_hub import snapshot_download as hf_snapshot_download

    try:
        from modelscope.hub.snapshot_download import (
            snapshot_download as ms_snapshot_download,
        )
    except ImportError:
        ms_snapshot_download = None

    from src.refinement.engine import RefinementEngine
except ImportError:
    hf_snapshot_download = None
    ms_snapshot_download = None
    RefinementEngine = None  # type: ignore

logger = logging.getLogger(__name__)


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

        # Determine initial model from config
        model_id = "qwen4b"
        if ConfigManager:
            model_id = (
                ConfigManager.get_config_value("refinement", "model_id") or "qwen4b"
            )

        self.current_model = MODELS.get(model_id, MODELS["qwen4b"])

        # Synchronization for User Input (non-blocking GPU confirmation)
        self._gpu_wait_condition = QWaitCondition()
        self._gpu_mutex = QMutex()
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

        if self._validate_artifacts(model_dir):
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
            # Or revert to DISABLED if we want to allow retry
            # self._set_state(SLMState.DISABLED)

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
            # Only emit busy signal if we are blocking or if we were blocking and now aren't
            # But we can just emit it always for simplicity or logic check
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

        # Make a copy to iterate, or use while loop pop(0)
        # Using pop(0) to maintain FIFO order
        while self._request_queue:
            # Re-check state in case a request puts us back into INFERRING or ERROR
            if self.state != SLMState.READY:
                break

            item = self._request_queue.pop(0)
            logger.debug(f"Processing queued request: {item}")

            # Helper to unpack kwargs if present
            if len(item) == 5:
                # Structure: (id, text, profile, instructions, kwargs_dict)
                tid, txt, prof, inst, kw = item
                self.handle_refinement_request(tid, txt, prof, inst, **kw)
            else:
                # Structure: (id, text, profile, instructions)
                self.handle_refinement_request(*item)

    def _get_gpu_memory_map(self) -> tuple[int, int] | None:
        """Get (total, free) GPU memory in MB via nvidia-smi."""
        try:
            # Check if nvidia-smi exists
            smi_path = shutil.which("nvidia-smi")
            if not smi_path:
                return None

            # Run nvidia-smi
            result = subprocess.check_output(
                [
                    smi_path,
                    "--query-gpu=memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                encoding="utf-8",
            )
            # Parse first line (assuming single GPU or taking first)
            lines = result.strip().split("\n")
            if not lines:
                return None

            total_str, free_str = lines[0].split(",")
            return int(total_str), int(free_str)
        except Exception as e:
            logger.warning(f"Failed to query GPU memory: {e}")
            return None

    def _start_gpu_confirmation_timeout(self):
        """Start a timeout timer for GPU confirmation dialog."""
        # Cancel any existing timer
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

        # Only proceed if we're still waiting for confirmation
        if self.state != SLMState.WAITING_FOR_USER:
            return

        # Continue initialization with CPU
        if (
            self._pending_init_model_dir is not None
            and self._pending_init_tokenizer_json is not None
        ):
            model_dir = self._pending_init_model_dir
            tokenizer_json = self._pending_init_tokenizer_json
            self._pending_init_model_dir = None
            self._pending_init_tokenizer_json = None

            self.statusMessage.emit("No response - using CPU for safety.")
            logger.info("Continuing initialization with CPU (timeout default)...")
            self._load_engine(model_dir, tokenizer_json, "cpu")

    @pyqtSlot(bool)
    def submit_gpu_choice(self, use_gpu: bool):
        """Receive user choice from main thread and continue initialization."""
        # Cancel timeout timer since user responded
        self._cancel_gpu_confirmation_timeout()

        self._gpu_mutex.lock()
        self._user_gpu_choice = use_gpu
        self._gpu_mutex.unlock()
        self._gpu_wait_condition.wakeAll()

        # Continue initialization if we were waiting for GPU confirmation
        if (
            self._pending_init_model_dir is not None
            and self._pending_init_tokenizer_json is not None
        ):
            model_dir = self._pending_init_model_dir
            tokenizer_json = self._pending_init_tokenizer_json
            self._pending_init_model_dir = None
            self._pending_init_tokenizer_json = None

            device = "cuda" if use_gpu else "cpu"
            logger.info(f"User chose: {device}. Continuing initialization...")
            self._load_engine(model_dir, tokenizer_json, device)

    def _validate_artifacts(self, model_dir: Path) -> bool:
        """Check if all required model artifacts exist."""
        if not model_dir.exists():
            return False

        # CTranslate2 can produce vocabulary.json OR vocabulary.txt, check loosely
        has_vocab = (model_dir / "vocabulary.json").exists() or (
            model_dir / "vocabulary.txt"
        ).exists()
        has_model = (model_dir / "model.bin").exists()
        has_config = (model_dir / "config.json").exists()

        if not (has_vocab and has_model and has_config):
            logger.warning(f"Missing artifacts in {model_dir}")
            return False

        return True

    @pyqtSlot()
    def initialize_service(self):
        """Called when feature is enabled or first used."""
        if self.state == SLMState.READY:
            return

        if self.state == SLMState.INFERRING:
            return

        self._set_state(SLMState.CHECKING_RESOURCES)

        # Check if refinement dependencies are available
        if RefinementEngine is None:
            logger.warning("Refinement dependencies not installed")
            self.statusMessage.emit(
                "Refinement unavailable: dependencies not installed"
            )
            self._set_state(SLMState.NOT_AVAILABLE)
            return

        try:
            cache_dir = get_model_cache_dir()
            model_dir = cache_dir / self.current_model.dir_name
            tokenizer_json = model_dir / "tokenizer.json"

            # Check if valid artifacts exist
            if not self._validate_artifacts(model_dir):
                logger.info("Model artifacts missing. Starting provisioning...")
                self.statusMessage.emit(
                    "⏳ First-run setup: Downloading and converting model. This may take several minutes..."
                )
                # Pause engine heartbeat to prevent timeout during long conversion
                self.requestHeartbeatPause.emit()
                self._start_background_provisioning(self.current_model)
                self._set_state(SLMState.DOWNLOADING_SOURCE)
                # Here we DO set state because we have no engine loaded, so we are blocked effectively
                return

            # Determine Device
            device = "cpu"

            mem_info = self._get_gpu_memory_map()
            if mem_info:
                total_mb, free_mb = mem_info
                # Size Estimate
                MODEL_SIZE_MB = self.current_model.required_vram_mb

                # Headroom calculation
                remaining_mb = free_mb - MODEL_SIZE_MB
                headroom_ratio = remaining_mb / total_mb

                logger.info(
                    f"GPU Info: Free={free_mb}MB, Total={total_mb}MB. Post-Load Headroom={headroom_ratio:.1%}"
                )

                if headroom_ratio >= 0.40:
                    # Safe -> Auto GPU
                    device = "cuda"
                    logger.info("Sufficient GPU headroom (>40%). Using CUDA.")
                elif headroom_ratio < 0.20:
                    # Risky -> Ask User (non-blocking with timeout)
                    self._set_state(SLMState.WAITING_FOR_USER)
                    logger.info(
                        "Low GPU headroom (<20%). Requesting user confirmation..."
                    )
                    # Store pending initialization state
                    self._pending_init_model_dir = model_dir
                    self._pending_init_tokenizer_json = tokenizer_json

                    # Start timeout timer - defaults to CPU if user doesn't respond
                    self._start_gpu_confirmation_timeout()

                    # Emit signal and return immediately (non-blocking)
                    self.askGPUConfirmation.emit(free_mb, total_mb, MODEL_SIZE_MB)
                    # Initialization will continue in submit_gpu_choice when user responds
                    # or in _on_gpu_confirmation_timeout if timer fires
                    return
                else:
                    # 20-40% -> Speed preference
                    device = "cuda"
                    logger.info(
                        "Moderate GPU headroom (20-40%). Defaulting to CUDA for speed."
                    )
            else:
                # No GPU info available, use CPU
                device = "cpu"
                logger.info("No GPU memory info available. Using CPU.")

            # Load Engine
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
            # Auto-initialize on first request
            self.statusMessage.emit("Initializing Refinement Service...")
            self.initialize_service()

        if self.state == SLMState.ERROR:
            self.refinementError.emit(
                transcript_id, "Refinement service is in error state."
            )
            return

        # If not ready, enqueue the request instead of rejecting it
        if self.state != SLMState.READY:
            logger.info(
                f"Service busy/loading ({self.state.value}). Enqueuing request {transcript_id}."
            )
            self._request_queue.append(
                (transcript_id, text, profile, user_instructions, kwargs)
            )
            self.statusMessage.emit("Request queued. Waiting for service...")
            return

        if not self._engine:
            self.refinementError.emit(transcript_id, "Engine not loaded.")
            return

        try:
            self._set_state(SLMState.INFERRING)
            self.statusMessage.emit(f"Refining transcript ({profile})...")

            result = self._engine.refine(text, profile, user_instructions, **kwargs)

            # Log reasoning if present
            if result.reasoning:
                logger.debug(
                    f"Refinement Reasoning [ID={transcript_id}]: {result.reasoning}"
                )

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
        if self.state is not SLMState.READY or not self._engine:
            logger.debug("MOTD generation skipped: SLM not ready or engine not loaded.")
            return

        logger.info("Generating new Message of the Day...")
        self._set_state(SLMState.INFERRING)

        # Run MOTD generation in background to avoid blocking UI
        worker = _MOTDWorker(self._engine)
        worker.signals.finished.connect(self._on_motd_generated)
        worker.signals.error.connect(self._on_motd_error)
        QThreadPool.globalInstance().start(worker)

    def _on_motd_generated(self, motd: str):
        """Handle successful MOTD generation."""
        logger.info("MOTD generation successful: %r", motd)
        self.motdReady.emit(motd)
        self._set_state(SLMState.READY)

    def _on_motd_error(self, error_msg: str):
        """Handle MOTD generation error."""
        logger.error(f"MOTD generation failed: {error_msg}")
        self._set_state(SLMState.READY)

    def _generate_motd_sync(self):
        """Synchronous MOTD generation logic (runs in worker thread)."""
        # DEPRECATED: This method body moved to _MOTDWorker.run()

    def _load_engine(self, model_path: Path, tokenizer_path: Path, device: str = "cpu"):
        """Load the Refinement Engine."""
        if RefinementEngine is None:
            logger.error("RefinementEngine not available (missing dependencies)")
            self.statusMessage.emit("Refinement unavailable: missing dependencies")
            self._set_state(SLMState.NOT_AVAILABLE)
            return

        self._set_state(SLMState.LOADING)
        self.statusMessage.emit(f"Loading engine on {device.upper()}...")
        try:
            # Load system prompt
            sys_prompt = ""
            invariants: list[str] = []
            levels: dict[int | str, dict[str, Any]] = {}
            if ConfigManager:
                sys_prompt = (
                    ConfigManager.get_config_value("prompts", "refinement_system") or ""
                )
                invariants = (
                    ConfigManager.get_config_value("prompts", "refinement_invariants")
                    or []
                )
                levels = (
                    ConfigManager.get_config_value("prompts", "refinement_levels") or {}
                )

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


# --- Background Workers ---


class _WorkerSignals(QObject):
    """Signals for background workers."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)


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
