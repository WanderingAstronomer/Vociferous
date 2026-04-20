"""Tests for support diagnostics snapshot logging."""

from __future__ import annotations

from unittest.mock import patch

from src.core.cuda_runtime import CudaRuntimeStatus
from src.core.log_manager import build_support_diagnostics_snapshot


class TestSupportDiagnosticsSnapshot:
    def test_snapshot_contains_support_relevant_sections(self, fresh_settings):
        with patch(
            "src.core.log_manager.detect_cuda_runtime",
            return_value=CudaRuntimeStatus(
                driver_detected=True,
                cuda_available=False,
                cuda_device_count=0,
                gpu_name="RTX 3080",
                vram_total_mb=10240,
                vram_free_mb=9728,
                detail="CUDA runtime unavailable",
            ),
        ):
            snapshot = build_support_diagnostics_snapshot(fresh_settings, transcript_count=12)

        assert snapshot["app"]["version"]
        assert snapshot["platform"]["system"]
        assert snapshot["python"]["version"]
        assert snapshot["cpu"]["logical_cores"] >= 1
        assert snapshot["gpu"]["gpu_name"] == "RTX 3080"
        assert snapshot["asr"]["model_id"] == fresh_settings.model.model
        assert snapshot["slm"]["model_id"] == fresh_settings.refinement.model_id
        assert snapshot["transcripts"]["count"] == 12

    def test_snapshot_does_not_dump_obviously_sensitive_process_details(self, fresh_settings):
        snapshot = build_support_diagnostics_snapshot(fresh_settings, transcript_count=1)

        serialized = str(snapshot)
        assert "system_prompt" not in serialized
        assert "invariants" not in serialized
        assert "HOME" not in serialized
