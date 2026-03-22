"""
AudioService unit tests.

Tests the pure computation and validation logic — NOT the PortAudio
hardware path (record_audio). Mocking an entire InputStream callback
chain would be testing mocks, not code.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.audio_service import AudioService, MicrophoneStatus


def _make_mock_sd(mock_sd, *, devices=None, default_input=None, default_input_exc=None, host_api=None, check_input_ok=True):
    """Wire up a mock sounddevice module with typical return values."""
    if devices is not None:
        def query_devices_side_effect(*args, **kwargs):
            if kwargs.get("kind") == "input":
                if default_input_exc:
                    raise default_input_exc
                return default_input
            return devices
        mock_sd.query_devices = MagicMock(side_effect=query_devices_side_effect)
    mock_sd.query_hostapis = MagicMock(return_value=host_api or {"name": "ALSA"})
    if check_input_ok:
        mock_sd.check_input_settings = MagicMock()
    else:
        mock_sd.check_input_settings = MagicMock(side_effect=sd_module.PortAudioError("unsupported format"))


# We need the real PortAudioError for check_input_settings mocking.
# sounddevice may not be installed in the test env, so fall back to a stub.
try:
    import sounddevice as sd_module
except ImportError:
    class _StubSD:
        class PortAudioError(Exception):
            pass
    sd_module = _StubSD()  # type: ignore[assignment]


@pytest.fixture()
def audio_service(fresh_settings):
    """AudioService without callbacks — just the computation engine."""
    return AudioService(
        settings_provider=lambda: fresh_settings,
        on_level_update=None,
    )


# ── detect_microphone ───────────────────────────────────────────────────


class TestDetectMicrophone:
    """Rich device detection returns MicrophoneStatus dataclass."""

    @patch("src.services.audio_service.sd")
    def test_no_devices(self, mock_sd):
        mock_sd.query_devices.return_value = []
        status = AudioService.detect_microphone()
        assert isinstance(status, MicrophoneStatus)
        assert status.available is False
        assert "no audio" in status.detail.lower()

    @patch("src.services.audio_service.sd")
    def test_no_input_devices(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2},
        ]
        status = AudioService.detect_microphone()
        assert status.available is False
        assert "no input" in status.detail.lower()

    @patch("src.services.audio_service.sd")
    def test_valid_device(self, mock_sd):
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "HDA Intel PCH", "max_input_channels": 2, "max_output_channels": 0}],
            default_input={"name": "HDA Intel PCH", "max_input_channels": 2, "default_samplerate": 48000.0, "hostapi": 0},
            host_api={"name": "PipeWire"},
        )
        status = AudioService.detect_microphone()
        assert status.available is True
        assert status.device_name == "HDA Intel PCH"
        assert status.host_api == "PipeWire"
        assert status.input_channels == 2
        assert status.default_sample_rate == 48000.0
        assert status.supports_16k is True
        assert "PipeWire" in status.detail

    @patch("src.services.audio_service.sd")
    def test_device_no_16k_support(self, mock_sd):
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Weird Mic", "max_input_channels": 1, "max_output_channels": 0}],
            default_input={"name": "Weird Mic", "max_input_channels": 1, "default_samplerate": 44100.0, "hostapi": 0},
            check_input_ok=False,
        )
        status = AudioService.detect_microphone()
        assert status.available is True
        assert status.supports_16k is False

    @patch("src.services.audio_service.sd")
    def test_default_input_query_fails(self, mock_sd):
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Mic", "max_input_channels": 1}],
            default_input_exc=RuntimeError("PulseAudio not running"),
        )
        status = AudioService.detect_microphone()
        assert status.available is False
        assert "cannot query" in status.detail.lower()

    @patch("src.services.audio_service.sd")
    def test_default_input_returns_none(self, mock_sd):
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Mic", "max_input_channels": 1}],
            default_input=None,
        )
        status = AudioService.detect_microphone()
        assert status.available is False
        assert "no default" in status.detail.lower()

    @patch("src.services.audio_service.sd")
    def test_sounddevice_completely_broken(self, mock_sd):
        mock_sd.query_devices.side_effect = OSError("ALSA lib not found")
        status = AudioService.detect_microphone()
        assert status.available is False
        assert "audio system error" in status.detail.lower()

    @patch("src.services.audio_service.sd")
    def test_zero_input_channels_on_default(self, mock_sd):
        """Default device reports 0 input channels (monitor/loopback)."""
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Monitor", "max_input_channels": 0}, {"name": "Mic", "max_input_channels": 1}],
            default_input={"name": "Monitor", "max_input_channels": 0, "default_samplerate": 48000.0, "hostapi": 0},
        )
        status = AudioService.detect_microphone()
        assert status.available is False
        assert "0 input channels" in status.detail


# ── validate_microphone ──────────────────────────────────────────────────


class TestValidateMicrophone:
    """Static microphone validation with mocked sounddevice."""

    @patch("src.services.audio_service.sd")
    def test_no_devices(self, mock_sd):
        """Empty device list → invalid."""
        mock_sd.query_devices.return_value = []
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "no microphone" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_no_input_devices(self, mock_sd):
        """Only output devices → invalid."""
        mock_sd.query_devices.return_value = [
            {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2},
        ]
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "no microphone" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_valid_input_device(self, mock_sd):
        """Working input device → valid."""
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Built-in Mic", "max_input_channels": 1, "max_output_channels": 0}],
            default_input={"name": "Built-in Mic", "max_input_channels": 1, "default_samplerate": 48000.0, "hostapi": 0},
        )
        valid, msg = AudioService.validate_microphone()
        assert valid is True
        assert msg == ""

    @patch("src.services.audio_service.sd")
    def test_default_input_fails(self, mock_sd):
        """Input devices exist but default can't be queried → invalid."""
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Mic", "max_input_channels": 1}],
            default_input_exc=RuntimeError("PulseAudio not running"),
        )
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "cannot query" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_default_input_returns_none(self, mock_sd):
        """query_devices(kind='input') returns None → invalid."""
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Mic", "max_input_channels": 1}],
            default_input=None,
        )
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "no default" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_sounddevice_completely_broken(self, mock_sd):
        """Total sounddevice failure → invalid with system error."""
        mock_sd.query_devices.side_effect = OSError("ALSA lib not found")
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "audio system error" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_no_16k_support(self, mock_sd):
        """Device exists but doesn't support 16 kHz → invalid with specific message."""
        _make_mock_sd(
            mock_sd,
            devices=[{"name": "Weird Mic", "max_input_channels": 1, "max_output_channels": 0}],
            default_input={"name": "Weird Mic", "max_input_channels": 1, "default_samplerate": 44100.0, "hostapi": 0},
            check_input_ok=False,
        )
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "16 khz" in msg.lower()
        assert "Weird Mic" in msg


# ── Constructor ─────────────────────────────────────────────────────────


class TestConstructor:
    """Init wires up callbacks correctly."""

    def test_sample_rate_default(self, audio_service):
        assert audio_service.sample_rate == 16000

    def test_callbacks_stored(self, fresh_settings):
        on_level = MagicMock()
        svc = AudioService(
            settings_provider=lambda: fresh_settings,
            on_level_update=on_level,
        )
        assert svc.on_level_update is on_level
