from __future__ import annotations

import sys
from types import SimpleNamespace

from src.core.runtime import server_window


class _FakeProcess:
    def __init__(self, pid: int | None = None) -> None:
        self.pid = 999 if pid is None else pid

    def cmdline(self) -> list[str]:
        return ["python", "other_app.py"]

    def username(self) -> str:
        return "drew"


def test_detect_port_conflict_reports_unknown_pid(monkeypatch) -> None:
    fake_psutil = SimpleNamespace(
        Process=_FakeProcess,
        net_connections=lambda kind: [
            SimpleNamespace(laddr=SimpleNamespace(port=18900), status="LISTEN", pid=None),
        ],
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    conflict, message = server_window._detect_port_conflict(18900)

    assert conflict is True
    assert "unknown process" in message
    assert "18900" in message


def test_detect_port_conflict_ignores_current_process(monkeypatch) -> None:
    fake_psutil = SimpleNamespace(
        Process=_FakeProcess,
        net_connections=lambda kind: [
            SimpleNamespace(laddr=SimpleNamespace(port=18900), status="LISTEN", pid=999),
        ],
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    assert server_window._detect_port_conflict(18900) == (False, "")


def test_detect_port_conflict_reports_other_process(monkeypatch) -> None:
    fake_psutil = SimpleNamespace(
        Process=_FakeProcess,
        net_connections=lambda kind: [
            SimpleNamespace(laddr=SimpleNamespace(port=18900), status="LISTEN", pid=1234),
        ],
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    conflict, message = server_window._detect_port_conflict(18900)

    assert conflict is True
    assert "PID 1234" in message
    assert "other_app.py" in message
    assert "Stop that process" in message
