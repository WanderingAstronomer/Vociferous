from __future__ import annotations

import types
from pathlib import Path

from src.core import engine_status
from src.core.cuda_runtime import CudaRuntimeStatus
from src.core.model_registry import ASR_MODELS, SLM_MODELS
from src.core.settings import init_settings, reset_for_tests


def _fake_cuda(**overrides: object) -> CudaRuntimeStatus:
    values = {
        "driver_detected": True,
        "cuda_available": True,
        "cuda_device_count": 1,
        "gpu_name": "RTX 3090",
        "vram_total_mb": 24576,
        "vram_used_mb": 1024,
        "vram_free_mb": 23552,
        "detail": "CUDA available",
    }
    values.update(overrides)
    return CudaRuntimeStatus(**values)


def test_normalize_engine_error_maps_missing_windows_cuda_dll() -> None:
    message = engine_status.normalize_engine_error("cublas64_12.dll is not found")

    assert "CUDA runtime DLLs" in message
    assert "pinned Windows CUDA runtime" in message


def test_build_engine_status_reports_missing_selected_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(engine_status, "detect_cuda_runtime", lambda: _fake_cuda())
    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "settings.json")
    coordinator = types.SimpleNamespace(
        settings=settings,
        recording_session=types.SimpleNamespace(
            is_asr_loaded=False,
            is_transcribing=False,
            last_asr_error=None,
            get_asr_runtime_summary=lambda: None,
        ),
        slm_runtime=None,
        is_recording_active=lambda: False,
    )

    status = engine_status.build_engine_status(coordinator)

    assert status["status"] == "missing_model"
    assert status["asr"]["state"] == "missing_model"
    assert status["slm"]["state"] == "missing_model"
    assert status["hardware"]["backend"] == "cuda"
    reset_for_tests()


def test_build_engine_status_reports_ready_models(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(engine_status, "detect_cuda_runtime", lambda: _fake_cuda())
    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "settings.json")

    models_dir = tmp_path / "cache" / "models"
    asr = ASR_MODELS[settings.model.model]
    slm = SLM_MODELS[settings.refinement.model_id]
    (models_dir / asr.repo.split("/")[-1]).mkdir(parents=True)
    (models_dir / asr.repo.split("/")[-1] / asr.model_file).touch()
    (models_dir / slm.repo.split("/")[-1]).mkdir(parents=True)
    (models_dir / slm.repo.split("/")[-1] / slm.model_file).touch()

    coordinator = types.SimpleNamespace(
        settings=settings,
        recording_session=types.SimpleNamespace(
            is_asr_loaded=True,
            is_transcribing=False,
            last_asr_error=None,
            get_asr_runtime_summary=lambda: {"resolved_device": "cuda"},
        ),
        slm_runtime=types.SimpleNamespace(
            state=types.SimpleNamespace(name="READY"),
            last_error=None,
            get_runtime_summary=lambda: {"resolved_device": "cuda"},
        ),
        is_recording_active=lambda: False,
    )

    status = engine_status.build_engine_status(coordinator)

    assert status["status"] == "ready"
    assert status["asr"]["ready"] is True
    assert status["slm"]["ready"] is True
    assert status["providers"][0]["id"] == "local_ct2"
    reset_for_tests()


def test_build_engine_status_reports_external_refinement_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(engine_status, "detect_cuda_runtime", lambda: _fake_cuda())
    reset_for_tests()


def test_build_engine_status_reports_external_transcription_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(engine_status, "detect_cuda_runtime", lambda: _fake_cuda())
    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "settings.json")
    settings = settings.model_copy(
        update={
            "model": settings.model.model_copy(
                update={
                    "provider": "groq",
                    "groq": settings.model.groq.model_copy(update={"model_id": "whisper-large-v3-turbo"}),
                }
            ),
            "refinement": settings.refinement.model_copy(update={"enabled": False}),
        }
    )

    coordinator = types.SimpleNamespace(
        settings=settings,
        recording_session=types.SimpleNamespace(
            is_asr_loaded=True,
            is_transcribing=False,
            last_asr_error=None,
            get_asr_runtime_summary=lambda: {
                "provider": "groq",
                "model_id": "whisper-large-v3-turbo",
                "resolved_device": "external",
                "base_url": "https://api.groq.com/openai/v1",
            },
        ),
        slm_runtime=None,
        is_recording_active=lambda: False,
    )

    status = engine_status.build_engine_status(coordinator)

    assert status["status"] == "ready"
    assert status["asr"]["ready"] is True
    assert status["asr"]["device"] == "external"
    assert status["asr"]["model_id"] == "whisper-large-v3-turbo"
    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "settings.json")
    settings.refinement.provider = "groq"
    settings.refinement.groq.model_id = "llama-3.1-8b-instant"

    models_dir = tmp_path / "cache" / "models"
    asr = ASR_MODELS[settings.model.model]
    (models_dir / asr.repo.split("/")[-1]).mkdir(parents=True)
    (models_dir / asr.repo.split("/")[-1] / asr.model_file).touch()

    coordinator = types.SimpleNamespace(
        settings=settings,
        recording_session=types.SimpleNamespace(
            is_asr_loaded=True,
            is_transcribing=False,
            last_asr_error=None,
            get_asr_runtime_summary=lambda: {"resolved_device": "cuda"},
        ),
        slm_runtime=types.SimpleNamespace(
            state=types.SimpleNamespace(name="READY"),
            last_error=None,
            get_runtime_summary=lambda: {
                "provider": "groq",
                "model_id": "llama-3.1-8b-instant",
                "resolved_device": "external",
                "base_url": "https://api.groq.com/openai/v1",
            },
        ),
        is_recording_active=lambda: False,
    )

    status = engine_status.build_engine_status(coordinator)

    assert status["status"] == "ready"
    assert status["slm"]["ready"] is True
    assert status["slm"]["device"] == "external"
    assert status["slm"]["model_id"] == "llama-3.1-8b-instant"
    assert [provider["id"] for provider in status["providers"]] == ["local_ct2", "lm_studio", "groq"]
    assert status["providers"][2]["active"] is True
    reset_for_tests()


def test_build_engine_status_reports_refinement_cpu_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(
        engine_status,
        "detect_cuda_runtime",
        lambda: _fake_cuda(driver_detected=False, cuda_available=False, cuda_device_count=0, gpu_name=""),
    )
    reset_for_tests()
    settings = init_settings(config_path=tmp_path / "settings.json")

    models_dir = tmp_path / "cache" / "models"
    asr = ASR_MODELS[settings.model.model]
    slm = SLM_MODELS[settings.refinement.model_id]
    (models_dir / asr.repo.split("/")[-1]).mkdir(parents=True)
    (models_dir / asr.repo.split("/")[-1] / asr.model_file).touch()
    (models_dir / slm.repo.split("/")[-1]).mkdir(parents=True)
    (models_dir / slm.repo.split("/")[-1] / slm.model_file).touch()

    coordinator = types.SimpleNamespace(
        settings=settings,
        recording_session=types.SimpleNamespace(
            is_asr_loaded=True,
            is_transcribing=False,
            last_asr_error=None,
            get_asr_runtime_summary=lambda: {"resolved_device": "cpu"},
        ),
        slm_runtime=types.SimpleNamespace(
            state=types.SimpleNamespace(name="READY"),
            last_error=None,
            get_runtime_summary=lambda: {"resolved_device": "cpu-fallback", "model_id": "qwen4b"},
        ),
        is_recording_active=lambda: False,
    )

    status = engine_status.build_engine_status(coordinator)

    assert status["slm"]["state"] == "ready"
    assert status["slm"]["ready"] is True
    assert status["slm"]["device"] == "cpu-fallback"
    assert "CPU" in status["slm"]["detail"]
    reset_for_tests()


def test_download_tracker_marks_idle_download_stalled(monkeypatch) -> None:
    engine_status._DOWNLOADS.clear()
    engine_status.track_download("asr", "large-v3", "started", "Starting")
    tracked = next(iter(engine_status._DOWNLOADS.values()))
    tracked.updated_at -= 999

    downloads = engine_status.get_tracked_downloads()

    assert downloads[0]["status"] == "stalled"
    assert "progress" in downloads[0]["message"]


def test_cleanup_engine_artifacts_removes_import_temp_files(monkeypatch, tmp_path: Path) -> None:
    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    stale = temp_dir / "vociferous_import_test.wav"
    stale.write_text("x", encoding="utf-8")
    monkeypatch.setenv("VOCIFEROUS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(engine_status, "tempfile_gettempdir", lambda: str(temp_dir))

    result = engine_status.cleanup_engine_artifacts()

    assert result["errors"] == []
    assert str(stale) in result["removed"]
    assert not stale.exists()