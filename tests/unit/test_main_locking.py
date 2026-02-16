"""Unit tests for single-instance lock handling in src.main."""

from pathlib import Path

from src import main as main_module


def _write_lock_artifacts(base: Path, pid: int) -> tuple[Path, Path]:
    pid_path = base / "vociferous-test-lock"
    lock_path = base / "vociferous-test-lock.lock"
    pid_path.write_text(str(pid))
    lock_path.write_text("lock")
    return pid_path, lock_path


def test_cleanup_stale_lock_removes_files_for_dead_pid(monkeypatch, tmp_path: Path) -> None:
    pid_path, lock_path = _write_lock_artifacts(tmp_path, 12345)
    monkeypatch.setenv("VOCIFEROUS_LOCK_PATH", str(pid_path))
    monkeypatch.setattr(main_module, "_should_break_lock_for_pid", lambda _pid: True)

    main_module._cleanup_stale_lock()

    assert not pid_path.exists()
    assert not lock_path.exists()


def test_cleanup_stale_lock_keeps_files_for_active_owner(monkeypatch, tmp_path: Path) -> None:
    pid_path, lock_path = _write_lock_artifacts(tmp_path, 12345)
    monkeypatch.setenv("VOCIFEROUS_LOCK_PATH", str(pid_path))
    monkeypatch.setattr(main_module, "_should_break_lock_for_pid", lambda _pid: False)

    main_module._cleanup_stale_lock()

    assert pid_path.exists()
    assert lock_path.exists()


def test_should_break_lock_for_stopped_vociferous_process(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "_is_pid_alive", lambda _pid: True)
    monkeypatch.setattr(main_module, "_get_unix_process_state", lambda _pid: "T")
    monkeypatch.setattr(main_module, "_is_vociferous_process", lambda _pid: True)

    assert main_module._should_break_lock_for_pid(9999) is True


def test_should_break_lock_for_reused_non_vociferous_pid(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "_is_pid_alive", lambda _pid: True)
    monkeypatch.setattr(main_module, "_get_unix_process_state", lambda _pid: "S")
    monkeypatch.setattr(main_module, "_is_vociferous_process", lambda _pid: False)

    assert main_module._should_break_lock_for_pid(9999) is True


def test_should_not_break_lock_for_active_vociferous_pid(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "_is_pid_alive", lambda _pid: True)
    monkeypatch.setattr(main_module, "_get_unix_process_state", lambda _pid: "S")
    monkeypatch.setattr(main_module, "_is_vociferous_process", lambda _pid: True)

    assert main_module._should_break_lock_for_pid(9999) is False


def test_release_lock_releases_and_cleans_pid_file(monkeypatch, tmp_path: Path) -> None:
    pid_path = tmp_path / "vociferous-test-lock"
    pid_path.write_text("123")
    monkeypatch.setenv("VOCIFEROUS_LOCK_PATH", str(pid_path))

    released = {"value": False}

    class DummyLock:
        def release(self) -> None:
            released["value"] = True

    setattr(main_module._acquire_lock, "_lock", DummyLock())

    main_module._release_lock()

    assert released["value"] is True
    assert not pid_path.exists()
    assert not hasattr(main_module._acquire_lock, "_lock")
