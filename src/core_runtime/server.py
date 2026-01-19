"""
Vociferous Engine Server.

The "Micro-Kernel" entry point. Runs the Transcription Engine in a separate process,
communicating with the UI via standard streams (stdin/stdout) or sockets.
"""

import sys
import threading
import logging
import time
from typing import Optional, BinaryIO

from src.core_runtime.protocol.transport import PacketTransport
from src.core_runtime.protocol.types import ProtocolMessage, MessageType
from src.core_runtime.engine import TranscriptionEngine
from src.core_runtime.types import TranscriptionResult
from src.core.config_manager import ConfigManager

# Configure logging to file/stderr (since stdout is used for transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Engine) %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class EngineServer:
    """
    Wraps the TranscriptionEngine with the IPC Protocol.
    """

    def __init__(self, reader: BinaryIO, writer: BinaryIO):
        self.transport = PacketTransport(reader, writer)
        self.engine: Optional[TranscriptionEngine] = None
        self.engine_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.running = True
        self.is_session_active = False  # Flag to track session intent across async load

        # Initialize Configuration (process-local)
        ConfigManager.initialize()

        # Guard for safe model loading across threads
        self._model_lock = threading.Lock()
        self.local_model = None

        # Start background preload immediately
        self.model_loader_thread = threading.Thread(
            target=self._preload_model_worker, daemon=True
        )
        self.model_loader_thread.start()

        # Start Heartbeat
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self.heartbeat_thread.start()

    def _ensure_model_loaded(self, notify: bool = True):
        """Thread-safe model loading with status reporting."""
        with self._model_lock:
            if self.local_model is not None:
                if notify:
                    self._send_status("model_ready")
                return

            logger.info("Loading Whisper Model...")
            if notify:
                self._send_status("loading_model")

            from src.services.transcription_service import create_local_model

            self.local_model = create_local_model()

            logger.info("Whisper Model Ready")
            if notify:
                self._send_status("model_ready")

    def _preload_model_worker(self):
        """Background worker to load the model at startup."""
        try:
            # We don't send status here because transport might not be ready/connected yet.
            # Ideally, we just load it. If it takes time, the first record attempt will wait.
            self._ensure_model_loaded(notify=False)
        except Exception:
            logger.exception("Background model preload failed")

    def _heartbeat_loop(self):
        """Send heartbeat every 1 second."""
        while self.running:
            try:
                self.transport.send_message(ProtocolMessage(MessageType.HEARTBEAT))
                time.sleep(1.0)
            except Exception:
                break

    def _init_engine(self):
        # We need a way to mock/inject model for headers/testing.
        # For real usage, we load the model.
        # But wait, loading model takes time. We should probably report status.

        # NOTE: faster_whisper import happens inside services usually to lazy load.
        # We'll rely on TranscriptionService's internal handling or inject None for now
        # and let the first run load it?
        # Actually, TranscriptionEngine takes `local_model`.

        # Let's import the service to get the model loader

        # We defer model loading to a background thread or first run to not block handshake
        self.local_model = None

    def start(self):
        """Start the command processing loop."""
        logger.info("Engine Server Starting...")
        try:
            while self.running:
                data = self.transport.receive()
                if data is None:
                    logger.info("Transport closed. Exiting.")
                    break

                if isinstance(data, ProtocolMessage):
                    self._handle_message(data)
                elif isinstance(data, bytes):
                    # We don't expect incoming audio currently (local mic is used by engine)
                    # Unless we support 'Audio Injection' mode later.
                    pass
        except KeyboardInterrupt:
            logger.info("Interrupted.")
        finally:
            self._shutdown()

    def _handle_message(self, msg: ProtocolMessage):
        logger.debug(f"Received: {msg.msg_type}")

        if msg.msg_type == MessageType.HANDSHAKE:
            # Enhanced Handshake
            msg.payload.get("version", "0.0")
            # In real logic, check version compatibility here

            self.transport.send_message(
                ProtocolMessage(
                    MessageType.HANDSHAKE_ACK,
                    {
                        "version": "1.0",
                        "status": "ready",
                        "engine_hash": "voci-engine-v1",  # Hardcoded for now
                        "capabilities": ["audio_stream", "vad", "gpu_support"],
                    },
                )
            )

        elif msg.msg_type == MessageType.START_SESSION:
            self._start_engine_thread()

        elif msg.msg_type == MessageType.STOP_SESSION:
            # Mark session as inactive so loading can abort if in progress
            self.is_session_active = False
            self._stop_recording()

        elif msg.msg_type == MessageType.UPDATE_CONFIG:
            self._handle_update_config(msg.payload)

        elif msg.msg_type == MessageType.SHUTDOWN:
            self.running = False
            self.is_session_active = False
            self._shutdown()

    def _handle_update_config(self, payload: dict):
        """Handle dynamic configuration updates from the client."""
        section = payload.get("section")
        key = payload.get("key")
        value = payload.get("value")

        if not section or not key:
            return

        logger.info(f"Updating engine config: {section}.{key} = {value}")
        ConfigManager.set_config_value(value, section, key)

        # If ASR model changed, force a reload to free memory and prep new model
        if section == "model_options" and key == "model":
            logger.info("ASR Model change detected. Invalidating current instance.")
            with self._model_lock:
                self.local_model = None

            # Optionally trigger background preload if not already active
            # This ensures the download starts immediately rather than waiting for first record
            threading.Thread(target=self._preload_model_worker, daemon=True).start()

    def _start_engine_thread(self):
        if self.engine_thread and self.engine_thread.is_alive():
            logger.warning("Session already running.")
            return

        self.is_session_active = True

        # Start the thread immediately. Model loading and pipeline run happen inside.
        self.engine_thread = threading.Thread(target=self._run_engine_lifecycle)
        self.engine_thread.daemon = True
        self.engine_thread.start()

    def _run_engine_lifecycle(self):
        """
        Thread target that handles the full session lifecycle:
        1. Load Model (heavy op)
        2. Create Engine
        3. Run Pipeline
        """
        # 1. Ensure Model is Loaded
        # Check cancellation before starting heavy load/wait
        if not self.is_session_active:
            return

        try:
            # If the background loader is running or we need to load, this calls with lock
            # If loading is already happening in background, this blocks until done.
            self._ensure_model_loaded(notify=True)
        except Exception as e:
            self._send_error(f"Model Load Failed: {e}")
            return

        # Check cancellation after load
        if not self.is_session_active:
            logger.info("Session cancelled after model load.")
            return

        # 2. Create Engine
        try:
            self.engine = TranscriptionEngine(
                local_model=self.local_model,
                on_result=self._on_engine_result,
                on_audio_level=self._on_audio_level,
                on_spectrum_update=self._on_spectrum_update,
            )
        except Exception as e:
            self._send_error(f"Engine Init Failed: {e}")
            return

        # 3. Run Pipeline
        self._run_engine_safely()

    def _run_engine_safely(self):
        try:
            if self.engine:
                self.engine.is_running = True
                self.engine.run_pipeline()
        except Exception as e:
            logger.exception("Engine Thread Crash")
            self._send_error(str(e))

    def _stop_recording(self):
        if self.engine:
            self.engine.stop_recording()

    def _shutdown(self):
        self.running = False
        if self.engine:
            self.engine.stop()
        self.transport.close()

    # --- Callbacks ---

    def _on_engine_result(self, result: TranscriptionResult):
        # Convert Enum to string for JSON
        payload = {
            "state": result.state.name,
            "text": result.text,
            "duration_ms": result.duration_ms,
            "speech_duration_ms": result.speech_duration_ms,
            "error_message": result.error_message,
        }
        self.transport.send_message(
            ProtocolMessage(MessageType.TRANSCRIPT_UPDATE, payload)
        )

    def _on_audio_level(self, level: float):
        self.transport.send_message(
            ProtocolMessage(MessageType.AUDIO_LEVEL, {"level": level})
        )

    def _on_spectrum_update(self, spectrum: list[float]):
        self.transport.send_message(
            ProtocolMessage(MessageType.AUDIO_SPECTRUM, {"spectrum": spectrum})
        )

    def _send_status(self, status: str):
        self.transport.send_message(
            ProtocolMessage(MessageType.STATUS_UPDATE, {"status": status})
        )

    def _send_error(self, message: str):
        self.transport.send_message(
            ProtocolMessage(MessageType.ERROR, {"message": message})
        )


if __name__ == "__main__":
    # Standard entry: Read from stdin, Write to stdout
    # MUST ensure stdout is binary mode for our transport
    server = EngineServer(sys.stdin.buffer, sys.stdout.buffer)
    server.start()
