"""
SLMRuntime state machine tests.

Validates lifecycle transitions: DISABLED→LOADING→READY→INFERRING and error paths.
No real model loading — all heavy I/O is mocked.
"""

from __future__ import annotations

import logging
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.services.slm_runtime import SLMRuntime
from src.services.slm_types import SLMState


@pytest.fixture()
def callbacks():
    """Shared MagicMock callbacks for tracking state transitions."""
    return {
        "on_state_changed": MagicMock(),
        "on_error": MagicMock(),
        "on_text_ready": MagicMock(),
    }


@pytest.fixture()
def runtime(fresh_settings, callbacks):
    """SLMRuntime with real settings but no model loading."""
    return SLMRuntime(
        settings_provider=lambda: fresh_settings,
        on_state_changed=callbacks["on_state_changed"],
        on_error=callbacks["on_error"],
        on_text_ready=callbacks["on_text_ready"],
    )


# ── State property and callback ───────────────────────────────────────────


class TestStateProperty:
    """State setter fires callback only on actual transitions."""

    def test_initial_state_is_disabled(self, runtime):
        assert runtime.state is SLMState.DISABLED

    def test_state_change_fires_callback(self, runtime, callbacks):
        runtime.state = SLMState.LOADING
        callbacks["on_state_changed"].assert_called_once_with(SLMState.LOADING)

    def test_same_state_does_not_fire_callback(self, runtime, callbacks):
        runtime.state = SLMState.DISABLED  # same as initial
        callbacks["on_state_changed"].assert_not_called()

    def test_no_callback_if_none(self, fresh_settings):
        """No crash if on_state_changed is None."""
        rt = SLMRuntime(
            settings_provider=lambda: fresh_settings,
            on_state_changed=None,
        )
        rt.state = SLMState.LOADING  # should not raise


# ── enable() ──────────────────────────────────────────────────────────────


class TestEnable:
    """enable() starts the loading thread from valid states only."""

    def test_enable_sets_loading_state(self, runtime, callbacks):
        with patch.object(runtime, "_load_model_task"):
            runtime.enable()
            # Give thread a moment to start
            import time

            time.sleep(0.05)
        assert callbacks["on_state_changed"].call_args_list[0][0][0] is SLMState.LOADING

    def test_enable_when_already_ready_is_noop(self, runtime, callbacks):
        runtime._state = SLMState.READY  # bypass setter
        runtime.enable()
        callbacks["on_state_changed"].assert_not_called()

    def test_enable_when_loading_is_noop(self, runtime, callbacks):
        runtime._state = SLMState.LOADING  # bypass setter
        runtime.enable()
        callbacks["on_state_changed"].assert_not_called()

    def test_enable_from_error_state_works(self, runtime, callbacks):
        runtime._state = SLMState.ERROR  # bypass setter
        with patch.object(runtime, "_load_model_task"):
            runtime.enable()
            import time

            time.sleep(0.05)
        assert callbacks["on_state_changed"].call_args_list[0][0][0] is SLMState.LOADING


# ── disable() ─────────────────────────────────────────────────────────────


class TestDisable:
    """disable() always transitions to DISABLED and unloads the engine."""

    def test_disable_from_ready(self, runtime, callbacks):
        runtime._state = SLMState.READY
        runtime._engine = MagicMock()
        runtime.disable()
        assert runtime.state is SLMState.DISABLED
        assert runtime._engine is None

    def test_disable_from_loading(self, runtime, callbacks):
        runtime._state = SLMState.LOADING
        runtime.disable()
        assert runtime.state is SLMState.DISABLED

    def test_disable_from_error(self, runtime, callbacks):
        runtime._state = SLMState.ERROR
        runtime.disable()
        assert runtime.state is SLMState.DISABLED

    def test_disable_from_disabled_is_noop(self, runtime, callbacks):
        """Already disabled — callback fires only if there was a real transition."""
        runtime.disable()
        # State was already DISABLED, setter skips callback
        callbacks["on_state_changed"].assert_not_called()


# ── refine_text() guard ──────────────────────────────────────────────────


class TestRefineTextGuard:
    """refine_text() only proceeds when state is READY."""

    def test_refine_when_disabled_is_noop(self, runtime):
        runtime.refine_text("test")
        assert runtime.state is SLMState.DISABLED

    def test_refine_when_loading_is_noop(self, runtime):
        runtime._state = SLMState.LOADING
        runtime.refine_text("test")
        assert runtime.state is SLMState.LOADING

    def test_refine_when_inferring_is_noop(self, runtime):
        runtime._state = SLMState.INFERRING
        runtime.refine_text("test")
        assert runtime.state is SLMState.INFERRING

    def test_refine_when_error_is_noop(self, runtime):
        runtime._state = SLMState.ERROR
        runtime.refine_text("test")
        assert runtime.state is SLMState.ERROR

    def test_refine_when_ready_transitions_to_inferring(self, runtime, callbacks):
        runtime._state = SLMState.READY
        runtime._engine = MagicMock()
        # Patch thread target so inference doesn't actually run
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            runtime.refine_text("test text")
        assert runtime.state is SLMState.INFERRING


# ── _inference_task (called directly, no threading) ──────────────────────


class TestInferenceTask:
    """_inference_task happy and error paths."""

    def test_inference_success_calls_on_text_ready(self, runtime, callbacks):
        mock_engine = MagicMock()
        mock_engine.refine.return_value = MagicMock(content="refined output")
        runtime._engine = mock_engine
        runtime._state = SLMState.INFERRING

        runtime._inference_task("raw text", level=1)

        callbacks["on_text_ready"].assert_called_once_with("refined output")
        assert runtime.state is SLMState.READY

    def test_inference_failure_calls_on_error(self, runtime, callbacks):
        mock_engine = MagicMock()
        mock_engine.refine.side_effect = RuntimeError("CUDA OOM")
        runtime._engine = mock_engine
        runtime._state = SLMState.INFERRING

        runtime._inference_task("raw text", level=1)

        callbacks["on_error"].assert_called_once()
        assert "CUDA OOM" in callbacks["on_error"].call_args[0][0]
        # State returns to READY even on failure (not ERROR)
        assert runtime.state is SLMState.READY

    def test_inference_with_no_engine_calls_on_error(self, runtime, callbacks):
        runtime._engine = None
        runtime._state = SLMState.INFERRING

        runtime._inference_task("text", level=1)

        callbacks["on_error"].assert_called_once()
        assert runtime.state is SLMState.READY


# ── _load_model_task error paths ──────────────────────────────────────────


class TestLoadModelTask:
    """_load_model_task error handling (called directly, no threading)."""

    def test_no_model_id_disables(self, runtime, fresh_settings, callbacks):
        """Empty model_id → back to DISABLED (not ERROR)."""
        fresh_settings.refinement.model_id = ""
        runtime._state = SLMState.LOADING

        runtime._load_model_task()

        assert runtime.state is SLMState.DISABLED

    def test_unknown_model_id_errors(self, runtime, fresh_settings, callbacks):
        """model_id not found in registry → ERROR state."""
        fresh_settings.refinement.model_id = "nonexistent-model-v9"
        runtime._state = SLMState.LOADING

        with patch("src.services.slm_runtime.get_slm_model", return_value=None):
            runtime._load_model_task()

        assert runtime.state is SLMState.ERROR
        callbacks["on_error"].assert_called_once()

    def test_missing_model_file_errors(self, runtime, fresh_settings, callbacks, tmp_path):
        """Model in registry but CT2 directory missing → ERROR state."""
        fresh_settings.refinement.model_id = "test-model"
        runtime._state = SLMState.LOADING

        mock_model = MagicMock()
        mock_model.repo = "org/nonexistent-ct2-model"
        mock_model.model_file = "model.bin"

        with (
            patch("src.services.slm_runtime.get_slm_model", return_value=mock_model),
            patch("src.core.resource_manager.ResourceManager.get_user_cache_dir", return_value=tmp_path),
        ):
            runtime._load_model_task()

        assert runtime.state is SLMState.ERROR
        callbacks["on_error"].assert_called_once()


# ── refine_text_sync ──────────────────────────────────────────────────────


class TestRefineTextSync:
    """Synchronous refinement — engine interactions."""

    def test_sync_refine_returns_content(self, runtime):
        mock_engine = MagicMock()
        mock_engine.refine.return_value = MagicMock(content="polished text")
        runtime._engine = mock_engine

        result = runtime.refine_text_sync("rough text", level=1)

        assert result == "polished text"
        mock_engine.refine.assert_called_once()

    def test_sync_refine_without_engine_raises(self, runtime):
        runtime._engine = None
        with pytest.raises(RuntimeError, match="Engine not loaded"):
            runtime.refine_text_sync("text")


# ── generate_custom_sync ──────────────────────────────────────────────────


class TestGenerateCustomSync:
    """Freeform generation — engine interactions."""

    def test_custom_generation_returns_content(self, runtime):
        mock_engine = MagicMock()
        mock_engine.generate_custom.return_value = MagicMock(content="generated")
        runtime._engine = mock_engine

        result = runtime.generate_custom_sync("system", "user prompt")

        assert result == "generated"
        mock_engine.generate_custom.assert_called_once()

    def test_custom_generation_without_engine_raises(self, runtime):
        runtime._engine = None
        with pytest.raises(RuntimeError, match="Engine not loaded"):
            runtime.generate_custom_sync("system", "prompt")


class TestTimingLogs:
    def test_refine_text_sync_logs_timing_context(self, runtime, caplog):
        caplog.set_level(logging.INFO, logger="src.services.slm_runtime")
        mock_engine = MagicMock()
        mock_engine.refine.return_value = MagicMock(content="polished text")
        runtime._engine = mock_engine
        runtime._runtime_summary = {
            "model_id": "qwen4b",
            "resolved_device": "cpu",
            "gpu_layers": 0,
            "cpu_threads": 4,
            "use_thinking": False,
        }

        with patch("src.services.slm_runtime.time.perf_counter", side_effect=[0.0, 2.5]):
            runtime.refine_text_sync("rough text for testing", level=1)

        assert "SLM refinement completed in 2.50s" in caplog.text
        assert "model=qwen4b" in caplog.text

    def test_slow_generate_custom_logs_warning(self, runtime, caplog):
        mock_engine = MagicMock()
        mock_engine.generate_custom.return_value = MagicMock(content="generated")
        runtime._engine = mock_engine
        runtime._runtime_summary = {
            "model_id": "qwen4b",
            "resolved_device": "cpu",
            "gpu_layers": 0,
            "cpu_threads": 4,
            "use_thinking": False,
        }

        with patch("src.services.slm_runtime.time.perf_counter", side_effect=[0.0, 20.0]):
            runtime.generate_custom_sync("system", "user prompt words here")

        assert "Slow SLM custom-generation detected" in caplog.text
        assert "elapsed=20.00s" in caplog.text


# ── change_model ──────────────────────────────────────────────────────────


class TestChangeModel:
    """change_model tears down and optionally re-enables."""

    def test_change_model_disables_and_re_enables(self, runtime, fresh_settings):
        """When refinement.enabled=True, changing model re-enables."""
        fresh_settings.refinement.enabled = True
        runtime._state = SLMState.READY
        runtime._engine = MagicMock()

        with (
            patch.object(runtime, "enable") as mock_enable,
            patch.object(runtime, "_settings_updater") as mock_updater,
        ):
            runtime.change_model("new-model-id")

        mock_updater.assert_called_once_with(refinement={"model_id": "new-model-id"})
        assert runtime.state is SLMState.DISABLED
        mock_enable.assert_called_once()

    def test_change_model_stays_disabled_when_not_enabled(self, runtime, fresh_settings):
        """When refinement.enabled=False, changing model stays disabled."""
        fresh_settings.refinement.enabled = False
        runtime._state = SLMState.READY
        runtime._engine = MagicMock()

        with (
            patch.object(runtime, "enable") as mock_enable,
            patch.object(runtime, "_settings_updater") as mock_updater,
        ):
            runtime.change_model("another-model")

        mock_updater.assert_called_once_with(refinement={"model_id": "another-model"})
        assert runtime.state is SLMState.DISABLED
        mock_enable.assert_not_called()
