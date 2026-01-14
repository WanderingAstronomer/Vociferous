import enum
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QMutex, QObject, QWaitCondition, pyqtSignal, pyqtSlot

# Conditional imports to defer dependencies until needed
try:
    from huggingface_hub import snapshot_download

    from refinement.engine import RefinementEngine
    from utils import get_model_cache_dir
except ImportError:
    snapshot_download = None
    RefinementEngine = None
    get_model_cache_dir = None

logger = logging.getLogger(__name__)


class SLMState(enum.Enum):
    DISABLED = "Disabled"
    CHECKING_RESOURCES = "Checking Resources"
    WAITING_FOR_USER = "Waiting for User"
    DOWNLOADING_SOURCE = "Downloading Source Model"
    CONVERTING_MODEL = "Converting Model"
    CLEANING_BUILD_DEPS = "Cleaning Build Deps"
    LOADING = "Loading Model"
    READY = "Ready"
    INFERRING = "Refining..."
    ERROR = "Error"


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

    refinementSuccess = pyqtSignal(int, str)  # transcript_id, text
    refinementError = pyqtSignal(int, str)  # transcript_id, error_message

    # Request Main Thread UI interaction
    askGPUConfirmation = pyqtSignal(int, int, int)  # free_mb, total_mb, needed_mb

    # Canonical Model Source of Truth
    SOURCE_REPO_ID = "Qwen/Qwen3-4B-Instruct-2507"
    SOURCE_REVISION = "main"

    # Artifact Layout
    MODEL_DIR_NAME = "qwen3-4b-ct2"
    SOURCE_DIR_NAME = "qwen3-source-temp"
    EXPECTED_ARTIFACTS = ["model.bin", "config.json", "vocabulary.json"]

    def __init__(self):
        super().__init__()
        self._state = SLMState.DISABLED
        self._engine: Optional[RefinementEngine] = None
        self._abort_download = False

        # Synchronization for User Input
        self._gpu_wait_condition = QWaitCondition()
        self._gpu_mutex = QMutex()
        self._user_gpu_choice = False

    @property
    def state(self) -> SLMState:
        return self._state

    def _set_state(self, new_state: SLMState):
        if self._state != new_state:
            self._state = new_state
            self.stateChanged.emit(new_state)
            self.statusMessage.emit(f"Refinement: {new_state.value}")

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

    @pyqtSlot(bool)
    def submit_gpu_choice(self, use_gpu: bool):
        """Receive user choice from main thread."""
        self._gpu_mutex.lock()
        self._user_gpu_choice = use_gpu
        self._gpu_mutex.unlock()
        self._gpu_wait_condition.wakeAll()

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

    def _install_build_deps(self):
        """Install dependencies required for conversion."""
        self.statusMessage.emit(
            "Installing build dependencies (torch, transformers)..."
        )
        logger.info("Installing build dependencies via pip...")
        try:
            # Install specific versions if needed, but for now standard latest should work
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "torch",
                    "transformers",
                    "sentencepiece",
                    "--no-warn-script-location",
                ]
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install build deps: {e}")
            raise

    def _uninstall_build_deps(self):
        """Uninstall build dependencies to keep environment clean."""
        self._set_state(SLMState.CLEANING_BUILD_DEPS)
        self.statusMessage.emit("Removing build dependencies...")
        logger.info("Uninstalling build dependencies...")
        try:
            subprocess.call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "uninstall",
                    "-y",
                    "torch",
                    "transformers",
                    "sentencepiece",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to uninstall build deps: {e}")

    def _run_conversion(self, source_dir: Path, output_dir: Path):
        """Run ctranslate2 conversion."""
        self._set_state(SLMState.CONVERTING_MODEL)
        self.statusMessage.emit("Converting model to CTranslate2 format...")
        logger.info(f"Converting model from {source_dir} to {output_dir}")

        # Try to locate the converter script in the same bin directory as python
        script_name = "ct2-transformers-converter"
        script_path = None

        # Look in likely locations
        possible_paths = [
            Path(sys.executable).parent / script_name,
            Path(sys.executable).parent / "Scripts" / f"{script_name}.exe",  # Windows
        ]

        for p in possible_paths:
            if p.exists():
                script_path = str(p)
                break

        if not script_path:
            # Fallback: assume in PATH
            script_path = script_name

        cmd = [
            script_path,
            "--model",
            str(source_dir),
            "--output_dir",
            str(output_dir),
            "--quantization",
            "int8",
            "--force",
        ]

        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e}")
            # Try module fallback if script failed (e.g. not in PATH)
            logger.info("Converter script execution failed, trying module execution...")
            cmd = [
                sys.executable,
                "-m",
                "ctranslate2.converters.transformers",
                "--model",
                str(source_dir),
                "--output_dir",
                str(output_dir),
                "--quantization",
                "int8",
                "--force",
            ]
            subprocess.check_call(cmd)

    def _provision_model(self, cache_dir: Path, model_dir: Path):
        """Full provisioning workflow: Download Source -> Convert -> Setup."""
        source_dir = cache_dir / self.SOURCE_DIR_NAME

        try:
            # 1. Download Source
            self._set_state(SLMState.DOWNLOADING_SOURCE)
            if not snapshot_download:
                raise ImportError("huggingface_hub not installed")

            self.statusMessage.emit("Downloading source model...")
            snapshot_download(
                repo_id=self.SOURCE_REPO_ID,
                local_dir=source_dir,
                revision=self.SOURCE_REVISION,
            )

            # 2. Install Build Deps
            self._install_build_deps()

            # 3. Convert
            self._run_conversion(source_dir, model_dir)

            # 4. Copy tokenizer.json (Required by GECEngine using tokenizers library)
            logger.info("Copying tokenizer artifacts...")
            source_tokenizer = source_dir / "tokenizer.json"
            if source_tokenizer.exists():
                shutil.copy2(source_tokenizer, model_dir / "tokenizer.json")
            else:
                logger.warning(
                    "tokenizer.json not found in source, refinement might fail."
                )

        except Exception as e:
            logger.error(f"Provisioning failed: {e}")
            # Clean up potentially corrupted output
            if model_dir.exists():
                shutil.rmtree(model_dir, ignore_errors=True)
            raise
        finally:
            # 5. Clean up Source and Deps
            if source_dir.exists():
                shutil.rmtree(source_dir, ignore_errors=True)
            self._uninstall_build_deps()

    @pyqtSlot()
    def initialize_service(self):
        """Called when feature is enabled or first used."""
        if self.state != SLMState.DISABLED:
            return

        self._set_state(SLMState.CHECKING_RESOURCES)

        try:
            cache_dir = get_model_cache_dir()
            model_dir = cache_dir / self.MODEL_DIR_NAME
            tokenizer_json = model_dir / "tokenizer.json"

            # Check if valid artifacts exist
            if not self._validate_artifacts(model_dir):
                logger.info(
                    "Model artifacts missing or incomplete. Starting provisioning..."
                )
                self._provision_model(cache_dir, model_dir)

            # Determine Device
            device = "cpu"

            mem_info = self._get_gpu_memory_map()
            if mem_info:
                total_mb, free_mb = mem_info
                # Qwen3-4B int8 size ~4.5GB
                MODEL_SIZE_MB = 4500

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
                    # Risky -> Ask User
                    self._set_state(SLMState.WAITING_FOR_USER)
                    logger.info(
                        "Low GPU headroom (<20%). Requesting user confirmation..."
                    )
                    self.askGPUConfirmation.emit(free_mb, total_mb, MODEL_SIZE_MB)

                    # Wait for response
                    self._gpu_mutex.lock()
                    self._gpu_wait_condition.wait(self._gpu_mutex)
                    use_gpu = self._user_gpu_choice
                    self._gpu_mutex.unlock()

                    device = "cuda" if use_gpu else "cpu"
                    logger.info(f"User chose: {device}")
                else:
                    # 20-40% -> Speed preference
                    device = "cuda"
                    logger.info(
                        "Moderate GPU headroom (20-40%). Defaulting to CUDA for speed."
                    )

            # Load Engine
            self._load_engine(model_dir, tokenizer_json, device)

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.statusMessage.emit(f"Setup Error: {str(e)[:50]}")
            self._set_state(SLMState.ERROR)

    @pyqtSlot(int, str, str)
    def handle_refinement_request(
        self, transcript_id: int, text: str, profile: str = "BALANCED"
    ):
        """Process a refinement request."""
        if self.state == SLMState.DISABLED:
            # Auto-initialize on first request
            self.initialize_service()

        if self.state == SLMState.ERROR:
            self.refinementError.emit(
                transcript_id, "Refinement service is in error state."
            )
            return

        if self.state != SLMState.READY:
            self.refinementError.emit(
                transcript_id, "Service preparing. Please wait..."
            )
            return

        if not self._engine:
            self.refinementError.emit(transcript_id, "Engine not loaded.")
            return

        try:
            self._set_state(SLMState.INFERRING)
            self.statusMessage.emit(f"Refining transcript ({profile})...")
            refined_text = self._engine.refine(text, profile)
            self.refinementSuccess.emit(transcript_id, refined_text)
            self._set_state(SLMState.READY)
            self.statusMessage.emit("Refinement complete.")
        except Exception as e:
            logger.error(f"Refinement error: {e}")
            self.refinementError.emit(transcript_id, f"Refinement failed: {str(e)}")
            self._set_state(SLMState.READY)

    def _load_engine(self, model_path: Path, tokenizer_path: Path, device: str = "cpu"):
        """Load the Refinement Engine."""
        self._set_state(SLMState.LOADING)
        self.statusMessage.emit(f"Loading engine on {device.upper()}...")
        try:
            self._engine = RefinementEngine(model_path, tokenizer_path, device=device)
            self._set_state(SLMState.READY)
            self.statusMessage.emit("Refinement engine ready.")
        except Exception as e:
            logger.error(f"Engine load failed: {e}")
            self._set_state(SLMState.ERROR)
            self.statusMessage.emit(f"Load Error: {str(e)[:40]}")
