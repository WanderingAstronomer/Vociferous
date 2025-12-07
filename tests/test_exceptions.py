"""Tests for domain-specific exceptions."""
import pytest

from vociferous.domain.exceptions import (
    VociferousError,
    EngineError,
    AudioDecodeError,
    ConfigurationError,
    SessionError,
    DependencyError,
)


def test_exception_hierarchy():
    """Test that all custom exceptions inherit from VociferousError."""
    assert issubclass(EngineError, VociferousError)
    assert issubclass(AudioDecodeError, VociferousError)
    assert issubclass(ConfigurationError, VociferousError)
    assert issubclass(SessionError, VociferousError)
    assert issubclass(DependencyError, VociferousError)


def test_vociferous_error_is_exception():
    """Test that VociferousError inherits from Exception."""
    assert issubclass(VociferousError, Exception)


def test_engine_error_can_be_raised():
    """Test that EngineError can be raised and caught."""
    with pytest.raises(EngineError, match="test error"):
        raise EngineError("test error")


def test_audio_decode_error_can_be_raised():
    """Test that AudioDecodeError can be raised and caught."""
    with pytest.raises(AudioDecodeError, match="decode failed"):
        raise AudioDecodeError("decode failed")


def test_configuration_error_can_be_raised():
    """Test that ConfigurationError can be raised and caught."""
    with pytest.raises(ConfigurationError, match="invalid config"):
        raise ConfigurationError("invalid config")


def test_session_error_can_be_raised():
    """Test that SessionError can be raised and caught."""
    with pytest.raises(SessionError, match="session error"):
        raise SessionError("session error")


def test_dependency_error_can_be_raised():
    """Test that DependencyError can be raised and caught."""
    with pytest.raises(DependencyError, match="missing dependency"):
        raise DependencyError("missing dependency")


def test_catch_vociferous_error():
    """Test that VociferousError catches all custom exceptions."""
    with pytest.raises(VociferousError):
        raise EngineError("engine error")
    
    with pytest.raises(VociferousError):
        raise AudioDecodeError("decode error")
    
    with pytest.raises(VociferousError):
        raise ConfigurationError("config error")
    
    with pytest.raises(VociferousError):
        raise SessionError("session error")
    
    with pytest.raises(VociferousError):
        raise DependencyError("dependency error")
