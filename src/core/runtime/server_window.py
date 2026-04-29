from __future__ import annotations

import logging
import platform
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.application_coordinator import ApplicationCoordinator

logger = logging.getLogger(__name__)


def _detect_port_conflict(port: int) -> tuple[bool, str]:
    """Detect if another process is using our port."""
    try:
        import psutil
    except ImportError:
        return False, ""

    try:
        current_pid = psutil.Process().pid
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == port and conn.status == "LISTEN":
                try:
                    proc = psutil.Process(conn.pid)
                    if proc.pid == current_pid:
                        continue

                    cmdline = " ".join(proc.cmdline())
                    username = proc.username()
                    msg = (
                        f"Port {port} is already in use by PID {conn.pid} ({username}).\n"
                        f"Command: {cmdline}\n\n"
                        f"To fix:\n"
                        f"  1. Kill the process: kill {conn.pid}\n"
                        f"  2. If unresponsive: kill -9 {conn.pid}\n"
                        f"  3. Or check with: ss -tlnp | grep {port}"
                    )
                    return True, msg
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    except Exception:
        logger.debug("Port conflict detection failed", exc_info=True)

    return False, ""


def start_api_server(coordinator: ApplicationCoordinator) -> None:
    """Start the Litestar API server in a background thread."""

    def run_server() -> None:
        import socket as socket_mod

        import uvicorn

        from src.api.app import create_app

        conflict, conflict_msg = _detect_port_conflict(18900)
        if conflict:
            logger.error(conflict_msg)
            return

        app = create_app(coordinator)
        sock = socket_mod.socket(socket_mod.AF_INET, socket_mod.SOCK_STREAM)
        sock.setsockopt(socket_mod.SOL_SOCKET, socket_mod.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", 18900))
        except OSError as exc:
            logger.error(
                "Cannot bind port 18900 — another process owns it. Kill the existing Vociferous instance manually: %s",
                exc,
            )
            sock.close()
            return

        try:
            config = uvicorn.Config(app, log_level="warning", log_config=None)
            server = uvicorn.Server(config)
            coordinator._uvicorn_server = server
            server.run(sockets=[sock])
        except Exception:
            logger.exception("API server failed")
        finally:
            try:
                sock.close()
            except OSError:
                pass

    coordinator._server_thread = threading.Thread(target=run_server, daemon=True, name="api-server")
    coordinator._server_thread.start()
    logger.info("API server starting on http://127.0.0.1:18900")


def wait_for_server(host: str = "127.0.0.1", port: int = 18900, timeout: float = 15.0) -> None:
    """Block until the API server is accepting TCP connections or timeout expires."""
    import socket
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                logger.info("API server ready (http://%s:%d)", host, port)
                return
        except OSError:
            time.sleep(0.05)
    logger.warning("API server did not become ready within %.1fs — opening window anyway", timeout)


def open_window(coordinator: ApplicationCoordinator) -> None:
    """Open the main pywebview window. Blocks until closed."""
    try:
        import webview

        if platform.system() == "Linux":
            try:
                from gi.repository import GLib

                GLib.set_prgname("vociferous")
                GLib.set_application_name("Vociferous")
            except Exception:
                logger.debug("Could not set GTK app identity", exc_info=True)

        from src.core.resource_manager import ResourceManager

        icon_path = ResourceManager.get_icon_path("vociferous_icon")

        def on_closing() -> bool:
            logger.info("Main window closing, initiating shutdown...")
            coordinator.shutdown(stop_server=True, close_windows=False)
            return True

        main_window: Any = webview.create_window(
            title="Vociferous",
            url="http://127.0.0.1:18900",
            width=1200,
            height=800,
            min_size=(800, 600),
            background_color="#1e1e1e",
        )
        coordinator._main_window = main_window
        coordinator.window.set_window(main_window)
        main_window.events.closing += on_closing
        main_window.events.maximized += coordinator.window.on_maximized
        main_window.events.restored += coordinator.window.on_restored

        webview.start(debug=False, icon=icon_path)
    except Exception:
        logger.exception("pywebview failed to start")
        coordinator.shutdown()
        raise RuntimeError("pywebview failed to start")
    finally:
        if not coordinator._shutdown_event.is_set():
            coordinator.shutdown(stop_server=False, close_windows=False)
