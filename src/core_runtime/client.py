"""
Engine Client.

Manages the child process for the Headless Engine and provides a
Pythonic API for the UI to interact with it.
"""

import sys
import subprocess
import threading
import logging
import time
from typing import Optional, Callable, Dict, Any

from .protocol.transport import PacketTransport, TransportError
from .protocol.types import ProtocolMessage, MessageType
from .types import EngineState, TranscriptionResult

logger = logging.getLogger(__name__)


class EngineClient:
    """
    Client-side IPC manager. Spawns and controls the Engine Server process.
    """

    def __init__(
        self,
        on_result: Callable[[TranscriptionResult], None],
        on_audio_level: Optional[Callable[[float], None]] = None,
        on_audio_spectrum: Optional[Callable[[list[float]], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        python_executable: str = sys.executable,
    ):
        self.on_result = on_result
        self.on_audio_level = on_audio_level
        self.on_audio_spectrum = on_audio_spectrum
        self.on_status = on_status
        self.python_exe = python_executable

        self.process: Optional[subprocess.Popen] = None
        self.transport: Optional[PacketTransport] = None
        self.listen_thread: Optional[threading.Thread] = None
        self.watchdog_thread: Optional[threading.Thread] = None
        self.running = False
        self._shutdown_requested = False  # Prevents recovery during shutdown

        self.last_heartbeat = 0.0
        self.heartbeat_timeout = 30.0  # Seconds (Increased for provisioning stability)
        self.heartbeat_paused = False
        self.connect_time = 0.0

    def pause_heartbeat(self):
        """Pause watchdog monitoring (e.g., during heavy startup)."""
        logger.info("Pausing Heartbeat Watchdog")
        self.heartbeat_paused = True

    def resume_heartbeat(self):
        """Resume watchdog monitoring."""
        logger.info("Resuming Heartbeat Watchdog")
        self.last_heartbeat = time.time()  # Reset timer
        self.heartbeat_paused = False

    def connect(self):
        """Spawn process and perform handshake."""
        if self.running:
            return

        cmd = [self.python_exe, "-m", "src.core_runtime.server"]
        logger.info(f"Spawning Engine: {cmd}")

        # Prepare Environment
        import os
        from pathlib import Path

        env = os.environ.copy()
        # Add project root to PYTHONPATH so 'src.*' imports work consistently
        project_root = str(Path(__file__).parent.parent.parent.resolve())
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_root}:{current_pythonpath}"
            if current_pythonpath
            else project_root
        )

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,  # Forward stderr for debug
                bufsize=0,  # Unbuffered for transport
                env=env,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to spawn engine: {e}")

        # Wrap pipes
        # Verify streams are available
        if not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Failed to capture process streams")

        self.transport = PacketTransport(self.process.stdout, self.process.stdin)
        self.running = True
        self.connect_time = time.time()
        self.last_heartbeat = time.time()

        # Start Listener Thread
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

        # Send Handshake
        self.transport.send_message(
            ProtocolMessage(
                MessageType.HANDSHAKE, {"version": "1.0", "client": "vociferous-ui"}
            )
        )

        # Start Watchdog
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

    def start_session(self):
        if not self.running or not self.transport:
            self.connect()
        self.transport.send_message(ProtocolMessage(MessageType.START_SESSION))

    def stop_session(self):
        if self.transport:
            self.transport.send_message(ProtocolMessage(MessageType.STOP_SESSION))

    def update_config(self, section: str, key: str, value: Any):
        """Forward a configuration update to the engine process."""
        if self.transport:
            self.transport.send_message(
                ProtocolMessage(
                    MessageType.UPDATE_CONFIG,
                    {"section": section, "key": key, "value": value},
                )
            )

    def shutdown(self):
        """Graceful shutdown — sets flag to prevent recovery, then cleans up."""
        self._shutdown_requested = True  # Signal recovery to abort
        self.running = False

        if self.transport:
            try:
                self.transport.send_message(ProtocolMessage(MessageType.SHUTDOWN))
            except TransportError:
                pass
            self.transport.close()

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                logger.warning("Engine did not terminate gracefully, forcing kill")
                self.process.kill()
            self.process = None

    def _listen_loop(self):
        logger.info("Client Listener Started")
        try:
            while self.running and self.transport:
                msg = self.transport.receive()
                if msg is None:
                    logger.warning("Transport EOF (Process died?)")
                    break

                if isinstance(msg, ProtocolMessage):
                    self._handle_message(msg)
        except Exception as e:
            logger.error(f"Client Listen Error: {e}")
        finally:
            self._handle_connection_loss()

    def _watchdog_loop(self):
        """Monitor heartbeats."""
        while self.running:
            time.sleep(1.0)
            if not self.running:
                break

            if self.heartbeat_paused:
                continue

            elapsed = time.time() - self.last_heartbeat
            if elapsed > self.heartbeat_timeout:
                logger.error(
                    f"Heartbeat Timeout ({elapsed:.1f}s > {self.heartbeat_timeout}s)"
                )
                self.running = False
                if self.transport:
                    try:
                        self.transport.close()
                    except Exception:
                        pass
                # _listen_loop will exit and trigger connection loss
                # Or we trigger it explicitly if listen loop is blocked?
                # Listen loop blocks on receive. If we close transport, receive should return/raise.
                break

    def _handle_connection_loss(self):
        # Check if shutdown was explicitly requested
        if self._shutdown_requested or not self.running:
            logger.info("Connection lost during shutdown, skipping recovery")
            return

        logger.warning("Connection Lost. Triggering Recovery...")
        self.running = False

        # Report Error
        self.on_result(
            TranscriptionResult(
                state=EngineState.ERROR, error_message="Engine Process Lost"
            )
        )

        # Avoid aggressive respawn if engine can't start (e.g., missing deps)
        if time.time() - self.connect_time < 5:
            logger.warning("Engine failed to start quickly, not retrying")
            return

        # Try to reconnect (only if shutdown not requested)
        if not self._shutdown_requested:
            logger.info("Attempting to reconnect to engine...")
            try:
                self.connect()
                logger.info("Reconnected to engine")
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")

    def _handle_message(self, msg: ProtocolMessage):
        # Update Heartbeat
        self.last_heartbeat = time.time()

        if msg.msg_type == MessageType.TRANSCRIPT_UPDATE:
            self._handle_transcript_update(msg.payload)
        elif msg.msg_type == MessageType.AUDIO_LEVEL:
            if self.on_audio_level:
                self.on_audio_level(msg.payload.get("level", 0.0))
        elif msg.msg_type == MessageType.AUDIO_SPECTRUM:
            if self.on_audio_spectrum:
                self.on_audio_spectrum(msg.payload.get("spectrum", []))
        elif msg.msg_type == MessageType.STATUS_UPDATE:
            if self.on_status:
                self.on_status(msg.payload.get("status", "unknown"))
        elif msg.msg_type == MessageType.ERROR:
            logger.error(f"Engine Error: {msg.payload.get('message')}")
            # Propagate as Error Result
            self.on_result(
                TranscriptionResult(
                    state=EngineState.ERROR,
                    error_message=msg.payload.get("message", "Unknown Error"),
                )
            )
        elif msg.msg_type == MessageType.HANDSHAKE_ACK:
            logger.info("Engine Handshake ACK Received")

    def _handle_transcript_update(self, payload: Dict[str, Any]):
        # Map back to TranscriptionResult
        state_str = payload.get("state", "IDLE")

        try:
            state = EngineState[state_str]
        except KeyError:
            state = EngineState.IDLE

        result = TranscriptionResult(
            state=state,
            text=payload.get("text", ""),
            duration_ms=payload.get("duration_ms", 0),
            speech_duration_ms=payload.get("speech_duration_ms", 0),
            error_message=payload.get("error_message", ""),
        )
        self.on_result(result)
