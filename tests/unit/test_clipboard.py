from __future__ import annotations

import subprocess

from src.core import clipboard


def test_linux_clipboard_tries_xsel_when_xclip_fails(monkeypatch) -> None:
    attempts: list[list[str]] = []

    monkeypatch.setattr(clipboard.platform, "system", lambda: "Linux")

    def fake_run(cmd: list[str], *, input: bytes, check: bool, timeout: int) -> subprocess.CompletedProcess:
        attempts.append(cmd)
        assert input == b"hello"
        assert check is True
        assert timeout == 3
        if cmd[0] == "xclip":
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    clipboard.copy_to_system_clipboard("hello")

    assert attempts == [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
